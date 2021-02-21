from itertools import groupby
from typing import List

from flask import Flask, jsonify
from flask_cors import CORS

from sqlalchemy.orm import Session

import database
from database import db_session
from models import CoinValue, Trade, ScoutHistory

app = Flask(__name__)
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.route('/api/value_history')
def value_history():
    session: Session
    with db_session() as session:
        values: List[CoinValue] = session.query(CoinValue).order_by(CoinValue.coin_id.asc(),
                                                                    CoinValue.datetime.asc()).all()
        coin_values = groupby(values, key=lambda cv: cv.coin)

        return jsonify({coin.symbol: [
            {"balance": entry.balance,
             "usd_value": entry.usd_value,
             "btc_value": entry.btc_value,
             "datetime": entry.datetime} for entry in history
        ] for coin, history in coin_values})


@app.route('/api/trade_history')
def trade_history():
    session: Session
    with db_session() as session:
        trades: List[Trade] = session.query(Trade).order_by(Trade.datetime.asc()).all()
        return jsonify([
            {"alt_coin": trade.alt_coin.symbol,
             "crypto_coin": trade.crypto_coin.symbol,
             "selling": trade.selling,
             "state": trade.state.value,
             "alt_starting_balance": trade.alt_starting_balance,
             "alt_trade_amount": trade.alt_trade_amount,
             "crypto_starting_balance": trade.crypto_starting_balance,
             "crypto_trade_amount": trade.crypto_trade_amount,
             "datetime": trade.datetime} for trade in trades])


@app.route('/api/scouting_history')
def scouting_history():
    session: Session
    with db_session() as session:
        scouts: List[ScoutHistory] = session.query(ScoutHistory).order_by(ScoutHistory.datetime.asc()).all()
        return jsonify([
            {
                "from_coin": scout.pair.from_coin.symbol,
                "to_coin": scout.pair.to_coin.symbol,
                "current_ratio": scout.current_ratio,
                "target_ratio": scout.target_ratio,
                "current_coin_price": scout.current_coin_price,
                "other_coin_price": scout.other_coin_price,
                "datetime": scout.datetime,
            } for scout in scouts
        ])


@app.route('/api/current_coin')
def current_coin():
    coin = database.get_current_coin()
    return coin.symbol if coin else None


if __name__ == '__main__':
    app.run(debug=True, port=5123)
