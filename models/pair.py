from sqlalchemy import Column, String, ForeignKey, Float, Integer
from sqlalchemy.orm import relationship

from .base import Base
from .coin import Coin


class Pair(Base):
    __tablename__ = "pairs"

    id = Column(Integer, primary_key=True)

    from_coin_id = Column(String, ForeignKey('coins.symbol'))
    from_coin = relationship("Coin", foreign_keys=[from_coin_id], lazy='joined')

    to_coin_id = Column(String, ForeignKey('coins.symbol'))
    to_coin = relationship("Coin", foreign_keys=[to_coin_id], lazy='joined')

    ratio = Column(Float)

    def __init__(self, from_coin: Coin, to_coin: Coin, ratio=None):
        self.from_coin = from_coin
        self.to_coin = to_coin
        self.ratio = ratio

    def __repr__(self):
        return f"<{self.from_coin_id}->{self.to_coin_id} :: {self.ratio}>"

    def info(self):
        return {"from_coin": self.from_coin.info(), "to_coin": self.to_coin.info(), "ratio": self.ratio}
