import time
from datetime import datetime, timedelta
from multiprocessing import Process, Value
from random import randint

import requests.exceptions
from binance.exceptions import BinanceAPIException
from diskcache import Cache

from .auto_trader import AutoTrader
from .binance_api_manager import BinanceAPIManager, AllTickers
from .config import Config
from .database import Database
from .logger import Logger
from .models import Coin

cache = Cache('.cache')


class FakeAllTickers(AllTickers):
    def __init__(self, manager: "MockBinanceManager"):
        self.manager = manager

    def get_price(self, ticker_symbol):
        return self.manager.get_market_ticker_price(ticker_symbol)


class MockBinanceManager(BinanceAPIManager):

    def __init__(self, config: Config, db: Database, logger: Logger, start_date: datetime = None, start_value=100):
        super().__init__(config, db, logger)
        self.config = config
        self.datetime = start_date or datetime(2021, 1, 1)
        self.balances = {config.BRIDGE.symbol: start_value}

    def increment(self, interval=1):
        self.datetime += timedelta(minutes=interval)

    def get_all_market_tickers(self):
        """
        Get ticker price of all coins
        """
        return FakeAllTickers(self)

    def get_market_ticker_price(self, ticker_symbol: str):
        """
        Get ticker price of a specific coin
        """
        dt = self.datetime.strftime("%d %b %Y %H:%M:%S")
        key = f"{ticker_symbol}_{dt}"
        val = cache.get(key, None)
        if val is None:
            try:
                val = float(self.BinanceClient.get_historical_klines(ticker_symbol, "1m", dt, dt)[0][1])
                cache.set(key, val)
            except requests.exceptions.ConnectionError:
                time.sleep(randint(5, 10))
                return self.get_market_ticker_price(ticker_symbol)

        return val

    def get_currency_balance(self, currency_symbol: str):
        """
        Get balance of a specific coin
        """
        return self.balances.get(currency_symbol, 0)

    def buy_alt(self, origin_coin: Coin, target_coin: Coin, all_tickers: AllTickers):
        origin_symbol = origin_coin.symbol
        target_symbol = target_coin.symbol

        origin_balance = self.get_currency_balance(origin_symbol)
        target_balance = self.get_currency_balance(target_symbol)
        from_coin_price = all_tickers.get_price(origin_symbol + target_symbol)

        order_quantity = self._buy_quantity(target_balance, from_coin_price, origin_symbol, target_symbol)
        target_quantity = order_quantity * from_coin_price
        self.balances[target_symbol] -= target_quantity
        self.balances[origin_symbol] = self.balances.get(origin_symbol, 0) + order_quantity * (
                1 - self.config.SCOUT_TRANSACTION_FEE)
        return {'price': from_coin_price}

    def sell_alt(self, origin_coin: Coin, target_coin: Coin):
        origin_symbol = origin_coin.symbol
        target_symbol = target_coin.symbol

        origin_balance = self.get_currency_balance(origin_symbol)
        from_coin_price = self.get_market_ticker_price(origin_symbol + target_symbol)

        order_quantity = self._sell_quantity(origin_balance, origin_symbol, target_symbol)
        target_quantity = order_quantity * from_coin_price
        self.balances[target_symbol] = self.balances.get(target_symbol, 0) + target_quantity * (
                1 - self.config.SCOUT_TRANSACTION_FEE)
        self.balances[origin_symbol] -= order_quantity
        return {'price': from_coin_price}


def backtest(start_date: datetime = None, end_date: datetime = None, interval=1, start_value=100, starting_coin: str = None):
    config = Config()
    logger = Logger()

    end_date = end_date or datetime.today()

    db = Database(logger, config, 'sqlite://')
    db.create_database()
    db.set_coins(config.SUPPORTED_COIN_LIST)

    manager = MockBinanceManager(config, db, logger, start_date, start_value)

    starting_coin = db.get_coin(starting_coin or config.SUPPORTED_COIN_LIST[0])
    manager.buy_alt(starting_coin, config.BRIDGE, manager.get_all_market_tickers())
    db.set_current_coin(starting_coin)

    trader = AutoTrader(manager, db, logger, config)
    trader.initialize_trade_thresholds()

    while manager.datetime < end_date:
        print(manager.datetime)
        trader.scout()
        manager.increment(interval)


def download_market_data(start_date: datetime = None, end_date: datetime = None, interval=1):
    def _thread(symbol, counter: Value):
        manager = MockBinanceManager(config, None, None, start_date)
        while manager.datetime < end_date:
            try:
                manager.get_market_ticker_price(symbol)
                manager.increment(interval)
                counter.value += 1
            except BinanceAPIException:
                time.sleep(randint(10, 30))

    config = Config()
    processes = []
    for coin in config.SUPPORTED_COIN_LIST:
        v = Value('i', 0)
        p = Process(target=_thread, args=(coin + config.BRIDGE.symbol, v))
        processes.append((coin, v, p))
        p.start()

    while True:
        total = sum(p[1].value for p in processes)
        avg = int(total / len(processes))
        print("Total datapoint count:", total)
        print("Average fetched per symbol:", avg)
        print("Average datetime:", datetime(2021, 1, 1) + timedelta(minutes=avg))
        time.sleep(5)
        print("")
