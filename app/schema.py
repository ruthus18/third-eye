from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Entity(BaseModel):

    class Config:
        orm_mode = True
        allow_mutation = False
        allow_population_by_field_name = True


class Currency(str, Enum):
    USD = 'USD'
    RUB = 'RUB'
    EUR = 'EUR'


class Instrument(Entity):
    name: str
    ticker: str
    figi: str
    currency: Currency
    price_increment: Decimal = Field(alias='minPriceIncrement')
