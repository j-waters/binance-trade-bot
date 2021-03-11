import random
from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session

from .binance_api_manager import BinanceAPIManager
from .config import Config
from .database import Database
from .logger import Logger
from .models import Pair, Coin, CoinValue


class AutoTrader:
    def __init__(self, binance_manager: BinanceAPIManager, database: Database, logger: Logger, config: Config):
        self.manager = binance_manager
        self.db = database
        self.logger = logger
        self.config = config

    def transaction_through_bridge(self, pair: Pair, all_tickers):
        '''
        Jump from the source coin to the destination coin through bridge coin
        '''
        if self.manager.sell_alt(pair.from_coin, self.config.BRIDGE) is None:
            self.logger.info("Couldn't sell, going back to scouting mode...")
            return None
        # This isn't pretty, but at the moment we don't have implemented logic to escape from a bridge coin... This'll do for now
        result = None
        while result is None:
            result = self.manager.buy_alt(pair.to_coin, self.config.BRIDGE, all_tickers)

        self.db.set_current_coin(pair.to_coin)
        self.update_trade_threshold(float(result[u'price']), all_tickers)

    def update_trade_threshold(self, current_coin_price: float, all_tickers):
        '''
        Update all the coins with the threshold of buying the current held coin
        '''
        current_coin = self.db.get_current_coin()

        if current_coin_price is None:
            self.logger.info("Skipping update... current coin {0} not found".format(current_coin + self.config.BRIDGE))
            return

        session: Session
        with self.db.db_session() as session:
            for pair in session.query(Pair).filter(Pair.to_coin == current_coin):
                from_coin_price = all_tickers.get_price(pair.from_coin + self.config.BRIDGE)

                if from_coin_price is None:
                    self.logger.info("Skipping update for coin {0} not found".format(pair.from_coin + self.config.BRIDGE))
                    continue

                pair.ratio = from_coin_price / current_coin_price

    def initialize_trade_thresholds(self):
        '''
        Initialize the buying threshold of all the coins for trading between them
        '''
        all_tickers = self.manager.get_all_market_tickers()

        session: Session
        with self.db.db_session() as session:
            for pair in session.query(Pair).filter(Pair.ratio == None).all():
                if not pair.from_coin.enabled or not pair.to_coin.enabled:
                    continue
                self.logger.info("Initializing {0} vs {1}".format(pair.from_coin, pair.to_coin))

                from_coin_price = all_tickers.get_price(pair.from_coin + self.config.BRIDGE)
                if from_coin_price is None:
                    self.logger.info("Skipping initializing {0}, symbol not found".format(pair.from_coin + self.config.BRIDGE))
                    continue

                to_coin_price = all_tickers.get_price(pair.to_coin + self.config.BRIDGE)
                if to_coin_price is None:
                    self.logger.info("Skipping initializing {0}, symbol not found".format(pair.to_coin + self.config.BRIDGE))
                    continue

                pair.ratio = from_coin_price / to_coin_price

    def initialize_current_coin(self):
        '''
        Decide what is the current coin, and set it up in the DB.
        '''
        if self.db.get_current_coin() is None:
            current_coin_symbol = self.config.CURRENT_COIN_SYMBOL
            if not current_coin_symbol:
                current_coin_symbol = random.choice(self.config.SUPPORTED_COIN_LIST)

            self.logger.info("Setting initial coin to {0}".format(current_coin_symbol))

            if current_coin_symbol not in self.config.SUPPORTED_COIN_LIST:
                exit("***\nERROR!\nSince there is no backup file, a proper coin name must be provided at init\n***")
            self.db.set_current_coin(current_coin_symbol)

            # if we don't have a configuration, we selected a coin at random... Buy it so we can start trading.
            if self.config.CURRENT_COIN_SYMBOL == '':
                current_coin = self.db.get_current_coin()
                self.logger.info("Purchasing {0} to begin trading".format(current_coin))
                all_tickers = self.manager.get_all_market_tickers()
                self.manager.buy_alt(current_coin, self.config.BRIDGE, all_tickers)
                self.logger.info("Ready to start trading")

    def scout(self):
        '''
        Scout for potential jumps from the current coin to another coin
        '''
        all_tickers = self.manager.get_all_market_tickers()

        current_coin = self.db.get_current_coin()
        # Display on the console, the current coin+Bridge, so users can see *some* activity and not thinkg the bot has stopped. Not logging though to reduce log size.
        print(str(
            datetime.now()) + " - CONSOLE - INFO - I am scouting the best trades. Current coin: {0} ".format(
            current_coin + self.config.BRIDGE), end='\r')

        current_coin_price = all_tickers.get_price(current_coin + self.config.BRIDGE)

        if current_coin_price is None:
            self.logger.info("Skipping scouting... current coin {0} not found".format(current_coin + self.config.BRIDGE))
            return

        ratio_dict: Dict[Pair, float] = {}

        for pair in self.db.get_pairs_from(current_coin):
            if not pair.to_coin.enabled:
                continue
            optional_coin_price = all_tickers.get_price(pair.to_coin + self.config.BRIDGE)

            if optional_coin_price is None:
                self.logger.info("Skipping scouting... optional coin {0} not found".format(pair.to_coin + self.config.BRIDGE))
                continue

            self.db.log_scout(pair, pair.ratio, current_coin_price, optional_coin_price)

            # Obtain (current coin)/(optional coin)
            coin_opt_coin_ratio = current_coin_price / optional_coin_price

            # save ratio so we can pick the best option, not necessarily the first
            ratio_dict[pair] = (coin_opt_coin_ratio - self.config.SCOUT_TRANSACTION_FEE *
                                self.config.SCOUT_MULTIPLIER * coin_opt_coin_ratio) - pair.ratio

        # keep only ratios bigger than zero
        ratio_dict = {k: v for k, v in ratio_dict.items() if v > 0}

        # if we have any viable options, pick the one with the biggest ratio
        if ratio_dict:
            best_pair = max(ratio_dict, key=ratio_dict.get)
            self.logger.info('Will be jumping from {0} to {1}'.format(
                current_coin, best_pair.to_coin_id))
            self.transaction_through_bridge(best_pair, all_tickers)

    def update_values(self):
        '''
        Log current value state of all altcoin balances against BTC and USDT in DB.
        '''
        all_ticker_values = self.manager.get_all_market_tickers()

        now = datetime.now()

        session: Session
        with self.db.db_session() as session:
            coins: List[Coin] = session.query(Coin).all()
            for coin in coins:
                balance = self.manager.get_currency_balance(coin.symbol)
                if balance == 0:
                    continue
                usd_value = all_ticker_values.get_price(coin + "USDT")
                btc_value = all_ticker_values.get_price(coin + "BTC")
                cv = CoinValue(coin, balance, usd_value, btc_value, datetime=now)
                session.add(cv)
                self.db.send_update(cv)
