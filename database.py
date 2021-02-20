import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Union, Optional

from socketio import Client
from socketio.exceptions import ConnectionError
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session, Session

from models import *

engine = create_engine("sqlite:///data/crypto_trading.db")

SessionMaker = sessionmaker(bind=engine)
SessionMaker()

socketio_client = Client()


def socketio_connect():
    if socketio_client.connected and socketio_client.namespaces:
        return True
    try:
        if not socketio_client.connected:
            socketio_client.connect('http://api:5123', namespaces=["/backend"])
        while not socketio_client.connected or not socketio_client.namespaces:
            time.sleep(0.1)
        return True
    except ConnectionError:
        return False


@contextmanager
def db_session():
    """
    Creates a context with an open SQLAlchemy session.
    """
    session: Session = scoped_session(SessionMaker)
    yield session
    session.commit()
    session.close()


def set_coins(symbols: List[str]):
    session: Session

    # Add coins to the database and set them as enabled or not
    with db_session() as session:
        # For all the coins in the database, if the symbol no longer appears
        # in the config file, set the coin as disabled
        coins: List[Coin] = session.query(Coin).all()
        for coin in coins:
            if coin.symbol not in symbols:
                coin.enabled = False

        # For all the symbols in the config file, add them to the database
        # if they don't exist
        for symbol in symbols:
            coin = next((coin for coin in coins if coin.symbol == symbol), None)
            if coin is None:
                session.add(Coin(symbol))
            else:
                coin.enabled = True

    # For all the combinations of coins in the database, add a pair to the database
    with db_session() as session:
        coins: List[Coin] = session.query(Coin).all()
        for from_coin in coins:
            for to_coin in coins:
                if from_coin != to_coin:
                    pair = session.query(Pair).filter(Pair.from_coin == from_coin, Pair.to_coin == to_coin).first()
                    if pair is None:
                        session.add(Pair(from_coin, to_coin))


def get_coin(coin: Union[Coin, str]) -> Coin:
    if type(coin) == Coin:
        return coin
    session: Session
    with db_session() as session:
        coin = session.query(Coin).get(coin)
        session.expunge(coin)
        return coin


def set_current_coin(coin: Union[Coin, str]):
    coin = get_coin(coin)
    session: Session
    with db_session() as session:
        if type(coin) == Coin:
            coin = session.merge(coin)
        cc = CurrentCoin(coin)
        session.add(cc)
        send_update(cc)


def get_current_coin() -> Optional[Coin]:
    session: Session
    with db_session() as session:
        current_coin = session.query(CurrentCoin).order_by(CurrentCoin.datetime.desc()).first()
        if current_coin is None:
            return None
        coin = current_coin.coin
        session.expunge(coin)
        return coin


def get_pair(from_coin: Union[Coin, str], to_coin: Union[Coin, str]):
    from_coin = get_coin(from_coin)
    to_coin = get_coin(to_coin)
    session: Session
    with db_session() as session:
        pair: Pair = session.query(Pair).filter(Pair.from_coin == from_coin, Pair.to_coin == to_coin).first()
        session.expunge(pair)
        return pair


def get_pairs_from(from_coin: Union[Coin, str]):
    from_coin = get_coin(from_coin)
    session: Session
    with db_session() as session:
        pairs: List[pair] = session.query(Pair).filter(Pair.from_coin == from_coin)
        return pairs


def log_scout(pair: Pair, target_ratio: float, current_coin_price: float, other_coin_price: float):
    session: Session
    with db_session() as session:
        pair = session.merge(pair)
        sh = ScoutHistory(pair, target_ratio, current_coin_price, other_coin_price)
        session.add(sh)
        send_update(sh)


def prune_scout_history(hours: float):
    time_diff = datetime.now() - timedelta(hours=hours)
    session: Session
    with db_session() as session:
        session.query(ScoutHistory).filter(ScoutHistory.datetime < time_diff).delete()


def prune_value_history():
    session: Session
    with db_session() as session:
        # Sets the first entry for each coin for each hour as 'hourly'
        hourly_entries: List[CoinValue] = session.query(CoinValue).group_by(
            CoinValue.coin_id, func.strftime('%H', CoinValue.datetime)).all()
        for entry in hourly_entries:
            entry.interval = Interval.HOURLY

        # Sets the first entry for each coin for each day as 'daily'
        daily_entries: List[CoinValue] = session.query(CoinValue).group_by(
            CoinValue.coin_id, func.date(CoinValue.datetime)).all()
        for entry in daily_entries:
            entry.interval = Interval.DAILY

        # Sets the first entry for each coin for each month as 'weekly' (Sunday is the start of the week)
        weekly_entries: List[CoinValue] = session.query(CoinValue).group_by(
            CoinValue.coin_id, func.strftime("%Y-%W", CoinValue.datetime)).all()
        for entry in weekly_entries:
            entry.interval = Interval.WEEKLY

        # The last 24 hours worth of minutely entries will be kept, so count(coins) * 1440 entries
        time_diff = datetime.now() - timedelta(hours=24)
        session.query(CoinValue).filter(CoinValue.interval == Interval.MINUTELY,
                                        CoinValue.datetime < time_diff).delete()

        # The last 28 days worth of hourly entries will be kept, so count(coins) * 672 entries
        time_diff = datetime.now() - timedelta(days=28)
        session.query(CoinValue).filter(CoinValue.interval == Interval.HOURLY,
                                        CoinValue.datetime < time_diff).delete()

        # The last years worth of daily entries will be kept, so count(coins) * 365 entries
        time_diff = datetime.now() - timedelta(days=365)
        session.query(CoinValue).filter(CoinValue.interval == Interval.DAILY,
                                        CoinValue.datetime < time_diff).delete()

        # All weekly entries will be kept forever


class TradeLog:
    def __init__(self, from_coin: Coin, to_coin: Coin, selling: bool):
        session: Session
        with db_session() as session:
            from_coin = session.merge(from_coin)
            to_coin = session.merge(to_coin)
            self.trade = Trade(from_coin, to_coin, selling)
            session.add(self.trade)
            # Flush so that SQLAlchemy fills in the id column
            session.flush()
            send_update(self.trade)

    def set_ordered(self, alt_starting_balance, crypto_starting_balance, alt_trade_amount):
        session: Session
        with db_session() as session:
            trade: Trade = session.merge(self.trade)
            trade.alt_starting_balance = alt_starting_balance
            trade.alt_trade_amount = alt_trade_amount
            trade.crypto_starting_balance = crypto_starting_balance
            trade.state = TradeState.ORDERED
            send_update(self.trade)

    def set_complete(self, crypto_trade_amount):
        session: Session
        with db_session() as session:
            trade: Trade = session.merge(self.trade)
            trade.crypto_trade_amount = crypto_trade_amount
            trade.state = TradeState.COMPLETE
            send_update(self.trade)


class TradeLog:
    def __init__(self, from_coin: Coin, to_coin: Coin, selling: bool):
        session: Session
        with db_session() as session:
            from_coin = session.merge(from_coin)
            to_coin = session.merge(to_coin)
            self.trade = Trade(from_coin, to_coin, selling)
            session.add(self.trade)

    def set_ordered(self, alt_starting_balance, crypto_starting_balance, alt_trade_amount):
        session: Session
        with db_session() as session:
            trade: Trade = session.merge(self.trade)
            trade.alt_starting_balance = alt_starting_balance
            trade.alt_trade_amount = alt_trade_amount
            trade.crypto_starting_balance = crypto_starting_balance
            trade.state = TradeState.ORDERED

    def set_complete(self, crypto_trade_amount):
        session: Session
        with db_session() as session:
            trade: Trade = session.merge(self.trade)
            trade.crypto_trade_amount = crypto_trade_amount
            trade.state = TradeState.COMPLETE


def create_database():
    Base.metadata.create_all(engine)


def send_update(model):
    if not socketio_connect():
        return

    socketio_client.emit('update', {
        "table": model.__tablename__,
        "data": model.info()
    }, namespace="/backend")


if __name__ == '__main__':
    create_database()
