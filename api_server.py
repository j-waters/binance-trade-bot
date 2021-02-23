from datetime import datetime
from itertools import groupby
from typing import List, Tuple

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from sqlalchemy import func
from sqlalchemy.orm import Session

import database
from database import db_session
from models import CoinValue, Trade, ScoutHistory, Coin, Pair, CurrentCoin

app = Flask(__name__)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*")


@app.route('/api/value_history/<coin>')
@app.route('/api/value_history')
def value_history(coin: str = None):
    session: Session
    with db_session() as session:
        values = session.query(CoinValue).order_by(CoinValue.coin_id.asc(),
                                                                    CoinValue.datetime.asc())

        if coin:
            values: List[CoinValue] = values.filter(CoinValue.coin_id == coin).all()
            return jsonify([entry.info() for entry in values])

        coin_values = groupby(values.all(), key=lambda cv: cv.coin)
        return jsonify({coin.symbol: [entry.info() for entry in history] for coin, history in coin_values})


@app.route('/api/total_value_history')
def total_value_history():
    session: Session
    with db_session() as session:
        total_values: List[Tuple[datetime, float, float]] = session.query(CoinValue.datetime,
                                                                          func.sum(CoinValue.btc_value),
                                                                          func.sum(CoinValue.usd_value)).group_by(
            CoinValue.datetime).all()
        return jsonify([{"datetime": tv[0], "btc": tv[1], "usd": tv[2]} for tv in total_values])


@app.route('/api/trade_history')
def trade_history():
    session: Session
    with db_session() as session:
        trades: List[Trade] = session.query(Trade).order_by(Trade.datetime.asc()).all()
        return jsonify([trade.info() for trade in trades])


@app.route('/api/scouting_history')
def scouting_history():
    current_coin = database.get_current_coin()
    coin = current_coin.symbol if current_coin is not None else None
    session: Session
    with db_session() as session:
        scouts: List[ScoutHistory] = session.query(ScoutHistory).join(ScoutHistory.pair).filter(
            Pair.from_coin_id == coin).order_by(ScoutHistory.datetime.asc()).all()
        return jsonify([scout.info() for scout in scouts])


@app.route('/api/current_coin')
def current_coin():
    coin = database.get_current_coin()
    return coin.info() if coin else None


@app.route('/api/current_coin_history')
def current_coin_history():
    session: Session
    with db_session() as session:
        current_coins: List[CurrentCoin] = session.query(CurrentCoin).all()
        return jsonify([cc.info() for cc in current_coins])


@app.route('/api/coins')
def coins():
    session: Session
    with db_session() as session:
        current_coin = session.merge(database.get_current_coin())
        coins: List[Coin] = session.query(Coin).all()
        return jsonify([{
            **coin.info(),
            "is_current": coin == current_coin
        } for coin in coins])


@app.route('/api/pairs')
def pairs():
    session: Session
    with db_session() as session:
        all_pairs: List[Pair] = session.query(Pair).all()
        return jsonify([pair.info() for pair in all_pairs])


@socketio.on('update', namespace='/backend')
def handle_my_custom_event(json):
    emit('update', json, namespace='/frontend', broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5123)
