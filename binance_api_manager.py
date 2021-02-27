import math
import time

from binance.client import Client
from binance.exceptions import BinanceAPIException

from database import TradeLog
from logger import Logger
from models import Coin


class BinanceAPIManager:
    def __init__(self, APIKey: str, APISecret: str, Tld: str, logger: Logger):
        self.BinanceClient = Client(APIKey, APISecret, None, Tld)
        self.logger = logger

    def get_all_market_tickers(self):
        """
        Get ticker price of all coins
        """
        return self.BinanceClient.get_all_tickers()

    def get_market_ticker_price(self, ticker_symbol: str):
        """
        Get ticker price of a specific coin
        """
        for ticker in self.BinanceClient.get_symbol_ticker():
            if ticker[u"symbol"] == ticker_symbol:
                return float(ticker[u"price"])
        return None

    def get_currency_balance(self, currency_symbol: str):
        """
        Get balance of a specific coin
        """
        for currency_balance in self.BinanceClient.get_account()[u"balances"]:
            if currency_balance[u"asset"] == currency_symbol:
                return float(currency_balance[u"free"])
        return None

    def first(self, iterable, condition=lambda x: True):
        try:
            return next(x for x in iterable if condition(x))
        except StopIteration:
            return None

    def get_market_ticker_price_from_list(self, all_tickers, ticker_symbol):
        '''
        Get ticker price of a specific coin
        '''
        ticker = self.first(all_tickers, condition=lambda x: x[u'symbol'] == ticker_symbol)
        return float(ticker[u'price']) if ticker else None

    def retry(self, func, *args, **kwargs):
        time.sleep(1)
        attempts = 0
        while attempts < 20:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.info("Failed to Buy/Sell. Trying Again.")
                if attempts == 0:
                    self.logger.info(e)
                attempts += 1
        return None

    def get_symbol_filter(self, alt_symbol: str, crypto_symbol: str, filter_type: str):
        return next(_filter for _filter in self.BinanceClient.get_symbol_info(alt_symbol + crypto_symbol)['filters']
                    if _filter['filterType'] == filter_type)

    def get_alt_tick(self, alt_symbol: str, crypto_symbol: str):
        step_size = self.get_symbol_filter(alt_symbol, crypto_symbol, 'LOT_SIZE')['stepSize']
        if step_size.find('1') == 0:
            return 1 - step_size.find('.')
        else:
            return step_size.find('1') - 1

    def get_min_notional(self, alt_symbol: str, crypto_symbol: str):
        return float(self.get_symbol_filter(alt_symbol, crypto_symbol, 'MIN_NOTIONAL')['minNotional'])

    def wait_for_order(self, alt_symbol, crypto_symbol, order_id):
        while True:
            try:
                time.sleep(3)
                stat = self.BinanceClient.get_order(symbol=alt_symbol + crypto_symbol, orderId=order_id)
                break
            except BinanceAPIException as e:
                self.logger.info(e)
                time.sleep(10)
            except Exception as e:
                self.logger.info("Unexpected Error: {0}".format(e))

        self.logger.info(stat)

        while stat[u'status'] != 'FILLED':
            try:
                stat = self.BinanceClient.get_order(
                    symbol=alt_symbol + crypto_symbol, orderId=order_id)
                time.sleep(1)
            except BinanceAPIException as e:
                self.logger.info(e)
                time.sleep(2)
            except Exception as e:
                self.logger.info("Unexpected Error: {0}".format(e))

        return stat

    def buy_alt(self, alt: Coin, crypto: Coin, all_tickers):
        return self.retry(self._buy_alt, alt, crypto, all_tickers)

    def _buy_alt(self, alt: Coin, crypto: Coin, all_tickers):
        """
        Buy altcoin
        """
        trade_log = TradeLog(alt, crypto, False)
        alt_symbol = alt.symbol
        crypto_symbol = crypto.symbol

        alt_tick = self.get_alt_tick(alt_symbol, crypto_symbol)

        alt_balance = self.get_currency_balance(alt_symbol)
        crypto_balance = self.get_currency_balance(crypto_symbol)
        from_coin_price = self.get_market_ticker_price_from_list(all_tickers, alt_symbol + crypto_symbol)

        order_quantity = math.floor(
            crypto_balance
            * 10 ** alt_tick
            / from_coin_price
        ) / float(10 ** alt_tick)
        self.logger.info("BUY QTY {0}".format(order_quantity))

        # Try to buy until successful
        order = None
        while order is None:
            try:
                order = self.BinanceClient.order_limit_buy(
                    symbol=alt_symbol + crypto_symbol,
                    quantity=order_quantity,
                    price=from_coin_price,
                )
                self.logger.info(order)
            except BinanceAPIException as e:
                self.logger.info(e)
                time.sleep(1)
            except Exception as e:
                self.logger.info("Unexpected Error: {0}".format(e))

        trade_log.set_ordered(alt_balance, crypto_balance, order_quantity)

        stat = self.wait_for_order(alt_symbol, crypto_symbol, order[u'orderId'])

        self.logger.info("Bought {0}".format(alt_symbol))

        trade_log.set_complete(stat["cummulativeQuoteQty"])

        return order

    def sell_alt(self, alt: Coin, crypto: Coin):
        return self.retry(self._sell_alt, alt, crypto)

    def _sell_alt(self, alt: Coin, crypto: Coin):
        """
        Sell altcoin
        """
        trade_log = TradeLog(alt, crypto, True)
        alt_symbol = alt.symbol
        crypto_symbol = crypto.symbol

        alt_tick = self.get_alt_tick(alt_symbol, crypto_symbol)

        order_quantity = math.floor(
            self.get_currency_balance(alt_symbol) * 10 ** alt_tick
        ) / float(10 ** alt_tick)
        self.logger.info("Selling {0} of {1}".format(order_quantity, alt_symbol))

        alt_balance = self.get_currency_balance(alt_symbol)
        crypto_balance = self.get_currency_balance(crypto_symbol)
        self.logger.info("Balance is {0}".format(alt_balance))
        order = None
        while order is None:
            order = self.BinanceClient.order_market_sell(
                symbol=alt_symbol + crypto_symbol, quantity=(order_quantity)
            )

        self.logger.info("order")
        self.logger.info(order)

        trade_log.set_ordered(alt_balance, crypto_balance, order_quantity)

        # Binance server can take some time to save the order
        self.logger.info("Waiting for Binance")
        time.sleep(5)

        stat = self.wait_for_order(alt_symbol, crypto_symbol, order[u'orderId'])

        new_balance = self.get_currency_balance(alt_symbol)
        while new_balance >= alt_balance:
            new_balance = self.get_currency_balance(alt_symbol)

        self.logger.info("Sold {0}".format(alt_symbol))

        trade_log.set_complete(stat["cummulativeQuoteQty"])

        return order
