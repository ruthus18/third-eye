import datetime as dt
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator

from .config import settings


class Entity(BaseModel):

    class Config:
        orm_mode = True
        allow_mutation = False
        allow_population_by_field_name = True


class Currency(str, Enum):
    USD = 'USD'
    RUB = 'RUB'
    EUR = 'EUR'

    def __str__(self) -> str:
        return self.value


class Instrument(Entity):
    figi: str
    name: str
    ticker: str
    currency: Currency
    price_increment: Decimal = Field(alias='minPriceIncrement')


class BalanceItem(Entity):
    currency: Currency
    balance: Decimal
    blocked: Optional[Decimal]


class CandleInterval(str, Enum):
    M1 = '1min'
    M5 = '5min'
    M10 = '10min'
    M30 = '30min'
    H1 = 'hour'
    D1 = 'day'
    D7 = 'week'
    D30 = 'month'

    def __str__(self) -> str:
        return self.value


class Candle(Entity):
    time: dt.datetime
    open: Decimal = Field(alias='o')
    high: Decimal = Field(alias='h')
    low: Decimal = Field(alias='l')
    close: Decimal = Field(alias='c')
    volume: int = Field(alias='v')

    @validator('time', pre=True, check_fields=False)
    @classmethod
    def datetime_to_local(cls, dt_str: str) -> dt.datetime:
        return dt.datetime.fromisoformat(dt_str.replace('Z', '+00:00')).astimezone(settings.TIMEZONE)


# class PortfolioItem(Entity):
#     instrument: Instrument
#     lots: int
