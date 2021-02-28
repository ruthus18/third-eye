from enum import Enum

from tortoise import Tortoise, fields, models

from .config import settings
from .schema import CandleInterval, Currency


async def init_db() -> None:
    await Tortoise.init(settings.TORTOISE_ORM)


async def db_size() -> str:
    conn = Tortoise.get_connection("default")
    _, result = await conn.execute_query(
        f"SELECT pg_database_size('{settings.DB_NAME}')/1024 AS kb_size;"
    )
    size_mb = result[0].get('kb_size') / 1024  # type: ignore
    return f'{size_mb:.3f} MB'


class InstrumentType(str, Enum):
    STOCK = 's'
    BOND = 'b'
    CURRENCY = 'c'


class Instrument(models.Model):
    figi = fields.CharField(max_length=12, pk=True)
    type = fields.CharEnumField(InstrumentType)

    name = fields.TextField()
    ticker = fields.CharField(max_length=16, unique=True)
    currency = fields.CharEnumField(Currency, default=Currency.USD)
    price_increment = fields.DecimalField(max_digits=5, decimal_places=2)

    imported_at = fields.DatetimeField(auto_now_add=True)
    deleted_at = fields.DatetimeField(null=True)

    def __str__(self) -> str:
        return f'[{self.ticker}] {self.name}'


class Candle(models.Model):
    id = fields.IntField(pk=True)
    instrument = fields.ForeignKeyField('models.Instrument', related_name='candles')

    interval = fields.CharEnumField(CandleInterval, max_length=6)

    time = fields.DatetimeField()
    open = fields.DecimalField(max_digits=8, decimal_places=2)
    high = fields.DecimalField(max_digits=8, decimal_places=2)
    low = fields.DecimalField(max_digits=8, decimal_places=2)
    close = fields.DecimalField(max_digits=8, decimal_places=2)
    volume = fields.IntField(max_digits=8, decimal_places=2)

    class Meta:
        indexes = (('instrument', 'interval', 'time'), )
        unique_together = (('instrument', 'interval', 'time'), )

    def __str__(self) -> str:
        return f'{self.time}'
