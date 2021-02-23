from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime, Integer
from sqlalchemy.orm import relationship

from .base import Base
from .coin import Coin


class CurrentCoin(Base):
    __tablename__ = "current_coin_history"
    id = Column(Integer, primary_key=True)
    coin_id = Column(String, ForeignKey('coins.symbol'))
    coin = relationship("Coin")
    datetime = Column(DateTime)

    def __init__(self, coin: Coin):
        self.coin = coin
        self.datetime = datetime.utcnow()

    def info(self):
        return {"datetime": self.datetime.isoformat(), "coin": self.coin.info()}
