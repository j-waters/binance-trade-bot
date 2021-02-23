#!python3
import configparser
import datetime
import json
import logging.handlers
import math
import os
import queue
import random
import time
from logging import Handler, Formatter
from typing import List, Dict

import requests
from binance.client import Client
from binance.exceptions import BinanceAPIException
from sqlalchemy.orm import Session

from database import set_coins, set_current_coin, get_current_coin, get_pairs_from, \
    db_session, create_database, get_pair, log_scout, TradeLog, CoinValue, prune_scout_history, prune_value_history, \
    send_update
from models import Coin, Pair
from scheduler import SafeScheduler

# Config consts
CFG_FL_NAME = 'user.cfg'
USER_CFG_SECTION = 'binance_user_config'

# Init config
config = configparser.ConfigParser()
config['DEFAULT'] = {
    'scout_transaction_fee': '0.001',
    'scout_multiplier': '5',
    'scout_sleep_time': '5'
}

if not os.path.exists(CFG_FL_NAME):
    print('No configuration file (user.cfg) found! See README.')
    exit()
config.read(CFG_FL_NAME)

# Logger setup
logger = logging.getLogger('crypto_trader_logger')
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh = logging.FileHandler('crypto_trading.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

# logging to console
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)

# Telegram bot
TELEGRAM_CHAT_ID = config.get(USER_CFG_SECTION, 'botChatID')
TELEGRAM_TOKEN = config.get(USER_CFG_SECTION, 'botToken')
BRIDGE_SYMBOL = config.get(USER_CFG_SECTION, 'bridge')
BRIDGE = Coin(BRIDGE_SYMBOL, False)

# Prune settings
SCOUT_HISTORY_PRUNE_TIME = float(config.get(USER_CFG_SECTION, 'hourToKeepScoutHistory', fallback="1"))

# Get config for scout
SCOUT_TRANSACTION_FEE = float(config.get(USER_CFG_SECTION, 'scout_transaction_fee'))
SCOUT_MULTIPLIER = float(config.get(USER_CFG_SECTION, 'scout_multiplier'))
SCOUT_SLEEP_TIME = int(config.get(USER_CFG_SECTION, 'scout_sleep_time'))

class RequestsHandler(Handler):
    def emit(self, record):
        log_entry = self.format(record)
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': log_entry,
            'parse_mode': 'HTML'
        }
        return requests.post("https://api.telegram.org/bot{token}/sendMessage".format(token=TELEGRAM_TOKEN),
                             data=payload).content


class LogstashFormatter(Formatter):
    def __init__(self):
        super(LogstashFormatter, self).__init__()

    def format(self, record):
        t = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        if isinstance(record.msg, dict):
            message = "<i>{datetime}</i>".format(datetime=t)

            for key in record.msg:
                message = message + (
                    "<pre>\n{title}: <strong>{value}</strong></pre>".format(title=key, value=record.msg[key]))

            return message
        else:
            return "<i>{datetime}</i><pre>\n{message}</pre>".format(message=record.msg, datetime=t)

# logging to Telegram if token exists
if TELEGRAM_TOKEN:
    que = queue.Queue(-1)  # no limit on size
    queue_handler = logging.handlers.QueueHandler(que)
    th = RequestsHandler()
    listener = logging.handlers.QueueListener(que, th)
    formatter = LogstashFormatter()
    th.setFormatter(formatter)
    logger.addHandler(queue_handler)
    listener.start()

logger.info('Started')

supported_coin_list = []

# Get supported coin list from supported_coin_list file
with open('supported_coin_list') as f:
    supported_coin_list = f.read().upper().splitlines()

# Init config
config = configparser.ConfigParser()
if not os.path.exists(CFG_FL_NAME):
    print('No configuration file (user.cfg) found! See README.')
    exit()
config.read(CFG_FL_NAME)


def retry(howmany):
    def tryIt(func):
        def f(*args, **kwargs):
            time.sleep(1)
            attempts = 0
            while attempts < howmany:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print("Failed to Buy/Sell. Trying Again.")
                    if attempts == 0:
                        logger.info(e)
                    attempts += 1
            return None

        return f

    return tryIt


def first(iterable, condition=lambda x: True):
    try:
        return next(x for x in iterable if condition(x))
    except StopIteration:
        return None


def get_all_market_tickers(client):
    '''
    Get ticker price of all coins
    '''
    return client.get_all_tickers()


def get_market_ticker_price(client, ticker_symbol):
    '''
    Get ticker price of a specific coin
    '''
    for ticker in client.get_symbol_ticker():
        if ticker[u'symbol'] == ticker_symbol:
            return float(ticker[u'price'])
    return None


def get_market_ticker_price_from_list(all_tickers, ticker_symbol):
    '''
    Get ticker price of a specific coin
    '''
    ticker = first(all_tickers, condition=lambda x: x[u'symbol'] == ticker_symbol)
    return float(ticker[u'price']) if ticker else None


def get_currency_balance(client: Client, currency_symbol: str):
    '''
    Get balance of a specific coin
    '''
    for currency_balance in client.get_account()[u'balances']:
        if currency_balance[u'asset'] == currency_symbol:
            return float(currency_balance[u'free'])
    return None


@retry(20)
def buy_alt(client: Client, alt: Coin, crypto: Coin):
    '''
    Buy altcoin
    '''
    trade_log = TradeLog(alt, crypto, False)
    alt_symbol = alt.symbol
    crypto_symbol = crypto.symbol
    ticks = {}
    for filt in client.get_symbol_info(alt_symbol + crypto_symbol)['filters']:
        if filt['filterType'] == 'LOT_SIZE':
            if filt['stepSize'].find('1') == 0:
                ticks[alt_symbol] = 1 - filt['stepSize'].find('.')
            else:
                ticks[alt_symbol] = filt['stepSize'].find('1') - 1
            break

    alt_balance = get_currency_balance(client, alt_symbol)
    crypto_balance = get_currency_balance(client, crypto_symbol)

    order_quantity = ((math.floor(crypto_balance *
                                  10 ** ticks[alt_symbol] / get_market_ticker_price(client,
                                                                                    alt_symbol + crypto_symbol)) / float(
        10 ** ticks[alt_symbol])))
    logger.info('BUY QTY {0}'.format(order_quantity))

    # Try to buy until successful
    order = None
    while order is None:
        try:
            order = client.order_limit_buy(
                symbol=alt_symbol + crypto_symbol,
                quantity=order_quantity,
                price=get_market_ticker_price(client, alt_symbol + crypto_symbol)
            )
            logger.info(order)
        except BinanceAPIException as e:
            logger.info(e)
            time.sleep(1)
        except Exception as e:
            logger.info("Unexpected Error: {0}".format(e))

    trade_log.set_ordered(alt_balance, crypto_balance, order_quantity)

    order_recorded = False
    while not order_recorded:
        try:
            time.sleep(3)
            stat = client.get_order(symbol=alt_symbol + crypto_symbol, orderId=order[u'orderId'])
            order_recorded = True
        except BinanceAPIException as e:
            logger.info(e)
            time.sleep(10)
        except Exception as e:
            logger.info("Unexpected Error: {0}".format(e))
    while stat[u'status'] != 'FILLED':
        try:
            stat = client.get_order(
                symbol=alt_symbol + crypto_symbol, orderId=order[u'orderId'])
            time.sleep(1)
        except BinanceAPIException as e:
            logger.info(e)
            time.sleep(2)
        except Exception as e:
            logger.info("Unexpected Error: {0}".format(e))

    logger.info('Bought {0}'.format(alt_symbol))

    trade_log.set_complete(stat['cummulativeQuoteQty'])

    return order


@retry(20)
def sell_alt(client: Client, alt: Coin, crypto: Coin):
    '''
    Sell altcoin
    '''
    trade_log = TradeLog(alt, crypto, True)
    alt_symbol = alt.symbol
    crypto_symbol = crypto.symbol
    ticks = {}
    for filt in client.get_symbol_info(alt_symbol + crypto_symbol)['filters']:
        if filt['filterType'] == 'LOT_SIZE':
            if filt['stepSize'].find('1') == 0:
                ticks[alt_symbol] = 1 - filt['stepSize'].find('.')
            else:
                ticks[alt_symbol] = filt['stepSize'].find('1') - 1
            break

    order_quantity = (math.floor(get_currency_balance(client, alt_symbol) *
                                 10 ** ticks[alt_symbol]) / float(10 ** ticks[alt_symbol]))
    logger.info('Selling {0} of {1}'.format(order_quantity, alt_symbol))

    alt_balance = get_currency_balance(client, alt_symbol)
    crypto_balance = get_currency_balance(client, crypto_symbol)
    logger.info('Balance is {0}'.format(alt_balance))
    order = None
    while order is None:
        order = client.order_market_sell(
            symbol=alt_symbol + crypto_symbol,
            quantity=(order_quantity)
        )

    logger.info('order')
    logger.info(order)

    trade_log.set_ordered(alt_balance, crypto_balance, order_quantity)

    # Binance server can take some time to save the order
    logger.info("Waiting for Binance")
    time.sleep(5)
    order_recorded = False
    stat = None
    while not order_recorded:
        try:
            time.sleep(3)
            stat = client.get_order(symbol=alt_symbol + crypto_symbol, orderId=order[u'orderId'])
            order_recorded = True
        except BinanceAPIException as e:
            logger.info(e)
            time.sleep(10)
        except Exception as e:
            logger.info("Unexpected Error: {0}".format(e))

    logger.info(stat)
    while stat[u'status'] != 'FILLED':
        logger.info(stat)
        try:
            stat = client.get_order(
                symbol=alt_symbol + crypto_symbol, orderId=order[u'orderId'])
            time.sleep(1)
        except BinanceAPIException as e:
            logger.info(e)
            time.sleep(2)
        except Exception as e:
            logger.info("Unexpected Error: {0}".format(e))

    newbal = get_currency_balance(client, alt_symbol)
    while (newbal >= alt_balance):
        newbal = get_currency_balance(client, alt_symbol)

    logger.info('Sold {0}'.format(alt_symbol))

    trade_log.set_complete(stat['cummulativeQuoteQty'])

    return order


def transaction_through_tether(client: Client, pair: Pair):
    '''
    Jump from the source coin to the destination coin through tether
    '''
    if sell_alt(client, pair.from_coin, BRIDGE) is None:
        logger.info("Couldn't sell, going back to scouting mode...")
        return None
    # This isn't pretty, but at the moment we don't have implemented logic to escape from a bridge coin... This'll do for now
    result = None
    while result is None:
        result = buy_alt(client, pair.to_coin, BRIDGE)

    set_current_coin(pair.to_coin)
    update_trade_threshold(client)


def update_trade_threshold(client: Client):
    '''
    Update all the coins with the threshold of buying the current held coin
    '''

    all_tickers = get_all_market_tickers(client)

    current_coin = get_current_coin()

    current_coin_price = get_market_ticker_price_from_list(all_tickers, current_coin + BRIDGE)

    if current_coin_price is None:
        logger.info("Skipping update... current coin {0} not found".format(current_coin + BRIDGE))
        return

    session: Session
    with db_session() as session:
        for pair in session.query(Pair).filter(Pair.to_coin == current_coin):
            from_coin_price = get_market_ticker_price_from_list(all_tickers, pair.from_coin + BRIDGE)

            if from_coin_price is None:
                logger.info("Skipping update for coin {0} not found".format(pair.from_coin + BRIDGE))
                continue

            pair.ratio = from_coin_price / current_coin_price


def initialize_trade_thresholds(client: Client):
    '''
    Initialize the buying threshold of all the coins for trading between them
    '''

    all_tickers = get_all_market_tickers(client)

    session: Session
    with db_session() as session:
        for pair in session.query(Pair).filter(Pair.ratio == None).all():
            if not pair.from_coin.enabled or not pair.to_coin.enabled:
                continue
            logger.info("Initializing {0} vs {1}".format(pair.from_coin, pair.to_coin))

            from_coin_price = get_market_ticker_price_from_list(all_tickers, pair.from_coin + BRIDGE)
            if from_coin_price is None:
                logger.info("Skipping initializing {0}, symbol not found".format(pair.from_coin + BRIDGE))
                continue

            to_coin_price = get_market_ticker_price_from_list(all_tickers, pair.to_coin + BRIDGE)
            if to_coin_price is None:
                logger.info("Skipping initializing {0}, symbol not found".format(pair.to_coin + BRIDGE))
                continue

            pair.ratio = from_coin_price / to_coin_price


def scout(client: Client, transaction_fee=0.001, multiplier=5):
    '''
    Scout for potential jumps from the current coin to another coin
    '''

    all_tickers = get_all_market_tickers(client)

    current_coin = get_current_coin()

    current_coin_price = get_market_ticker_price_from_list(all_tickers, current_coin + BRIDGE)

    if current_coin_price is None:
        logger.info("Skipping scouting... current coin {0} not found".format(current_coin + BRIDGE))
        return

    ratio_dict: Dict[Pair, float] = {}

    for pair in get_pairs_from(current_coin):
        if not pair.to_coin.enabled:
            continue
        optional_coin_price = get_market_ticker_price_from_list(all_tickers, pair.to_coin + BRIDGE)

        if optional_coin_price is None:
            logger.info("Skipping scouting... optional coin {0} not found".format(pair.to_coin + BRIDGE))
            continue

        log_scout(pair, pair.ratio, current_coin_price, optional_coin_price)

        # Obtain (current coin)/(optional coin)
        coin_opt_coin_ratio = current_coin_price / optional_coin_price

        # save ratio so we can pick the best option, not necessarily the first
        ratio_dict[pair] = (coin_opt_coin_ratio - transaction_fee * multiplier * coin_opt_coin_ratio) - pair.ratio

    # keep only ratios bigger than zero
    ratio_dict = {k: v for k, v in ratio_dict.items() if v > 0}

    # if we have any viable options, pick the one with the biggest ratio
    if ratio_dict:
        best_pair = max(ratio_dict, key=ratio_dict.get)
        logger.info('Will be jumping from {0} to {1}'.format(
            current_coin, best_pair.to_coin_id))
        transaction_through_tether(
            client, best_pair)


def update_values(client: Client):
    all_ticker_values = get_all_market_tickers(client)

    now = datetime.datetime.now()

    session: Session
    with db_session() as session:
        coins: List[Coin] = session.query(Coin).all()
        for coin in coins:
            balance = get_currency_balance(client, coin.symbol)
            if balance == 0:
                continue
            usd_value = get_market_ticker_price_from_list(all_ticker_values, coin + "USDT")
            btc_value = get_market_ticker_price_from_list(all_ticker_values, coin + "BTC")
            cv = CoinValue(coin, balance, usd_value, btc_value, datetime=now)
            session.add(cv)
            send_update(cv)


def migrate_old_state():
    if os.path.isfile('.current_coin'):
        with open('.current_coin', 'r') as f:
            coin = f.read().strip()
            logger.info(f".current_coin file found, loading current coin {coin}")
            set_current_coin(coin)
        os.rename('.current_coin', '.current_coin.old')
        logger.info(f".current_coin renamed to .current_coin.old - You can now delete this file")

    if os.path.isfile('.current_coin_table'):
        with open('.current_coin_table', 'r') as f:
            logger.info(f".current_coin_table file found, loading into database")
            table: dict = json.load(f)
            session: Session
            with db_session() as session:
                for from_coin, to_coin_dict in table.items():
                    for to_coin, ratio in to_coin_dict.items():
                        if from_coin == to_coin:
                            continue
                        pair = session.merge(get_pair(from_coin, to_coin))
                        pair.ratio = ratio
                        session.add(pair)

        os.rename('.current_coin_table', '.current_coin_table.old')
        logger.info(f".current_coin_table renamed to .current_coin_table.old - You can now delete this file")


def main():
    api_key = config.get(USER_CFG_SECTION, 'api_key')
    api_secret_key = config.get(USER_CFG_SECTION, 'api_secret_key')
    tld = config.get(USER_CFG_SECTION, 'tld') or 'com' # Default Top-level domain is 'com'

    client = Client(api_key, api_secret_key, tld=tld)

    logger.info("Creating database schema if it doesn't already exist")
    create_database()

    set_coins(supported_coin_list)

    migrate_old_state()

    initialize_trade_thresholds(client)

    if get_current_coin() is None:
        current_coin_symbol = config.get(USER_CFG_SECTION, 'current_coin')
        if not current_coin_symbol:
            current_coin_symbol = random.choice(supported_coin_list)

        logger.info("Setting initial coin to {0}".format(current_coin_symbol))

        if current_coin_symbol not in supported_coin_list:
            exit("***\nERROR!\nSince there is no backup file, a proper coin name must be provided at init\n***")
        set_current_coin(current_coin_symbol)

        if config.get(USER_CFG_SECTION, 'current_coin') == '':
            current_coin = get_current_coin()
            logger.info("Purchasing {0} to begin trading".format(current_coin))
            buy_alt(client, current_coin, BRIDGE)
            logger.info("Ready to start trading")

    schedule = SafeScheduler(logger)
    schedule.every(SCOUT_SLEEP_TIME).seconds.do(scout,
                                                client=client,
                                                transaction_fee=SCOUT_TRANSACTION_FEE,
                                                multiplier=SCOUT_MULTIPLIER).tag("scouting")
    schedule.every(1).minutes.do(update_values, client=client).tag("updating value history")
    schedule.every(1).minutes.do(prune_scout_history, hours=SCOUT_HISTORY_PRUNE_TIME).tag("pruning scout history")
    schedule.every(1).hours.do(prune_value_history).tag("pruning value history")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
