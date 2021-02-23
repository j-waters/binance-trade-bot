from itertools import groupby
from typing import List

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from sqlalchemy.orm import Session

import database
from database import db_session
from models import CoinValue, Trade, ScoutHistory, Coin

app = Flask(__name__)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*")


@app.route('/api/value_history')
def value_history():
    session: Session
    with db_session() as session:
        values: List[CoinValue] = session.query(CoinValue).order_by(CoinValue.coin_id.asc(),
                                                                    CoinValue.datetime.asc()).all()
        coin_values = groupby(values, key=lambda cv: cv.coin)

        return jsonify({coin.symbol: [entry.info() for entry in history] for coin, history in coin_values})


@app.route('/api/trade_history')
def trade_history():
    session: Session
    with db_session() as session:
        trades: List[Trade] = session.query(Trade).order_by(Trade.datetime.asc()).all()
        return jsonify([trade.info() for trade in trades])


@app.route('/api/scouting_history')
def scouting_history():
    session: Session
    with db_session() as session:
        scouts: List[ScoutHistory] = session.query(ScoutHistory).order_by(ScoutHistory.datetime.asc()).all()
        return jsonify([scout.info() for scout in scouts])


@app.route('/api/current_coin')
def current_coin():
    coin = database.get_current_coin()
    return coin.info() if coin else None


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


@socketio.on('update', namespace='/backend')
def handle_my_custom_event(json):
    emit('update', json, namespace='/frontend', broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5123)
