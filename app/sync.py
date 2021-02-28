import logging

from tortoise import timezone as tz

from . import models
from .schema import Currency
from .tinkoff import TinkoffClient

logger = logging.getLogger(__name__)


async def main() -> None:
    await models.init_db()
    client = TinkoffClient()

    logger.info('Importing currencies...')
    await sync_currencies(client)

    logger.info('Importing stocks...')
    await sync_stocks(client)

    logger.info('Importing day candles...')
    await sync_day_candles(client)

    logger.info('All done!')

    await client.close()


async def sync_currencies(client: TinkoffClient) -> None:
    new_currencies = 0
    for currency in await client.get_currencies():
        _, is_new = await models.Instrument.get_or_create(
            figi=currency.figi,
            defaults={
                'type': models.InstrumentType.CURRENCY,
                'name': currency.name,
                'ticker': currency.ticker,
                'currency': currency.currency,
                'price_increment': currency.price_increment,
            }
        )
        if is_new:
            new_currencies += 1

    if new_currencies > 0:
        logger.info('New currencies uploaded: %s', new_currencies)


async def sync_stocks(client: TinkoffClient) -> None:
    stock_objs = {
        obj.figi: obj for obj in await client.get_stocks() if obj.currency == Currency.USD
    }

    stock_ids = set(stock_objs.keys())
    db_stock_ids = set(
        await models.Instrument
        .filter(type=models.InstrumentType.STOCK, currency=Currency.USD, deleted_at__isnull=True)
        .values_list('figi', flat=True)
    )
    to_create_ids = stock_ids - db_stock_ids
    to_delete_ids = db_stock_ids - stock_ids

    to_create_instances = []
    for figi in to_create_ids:
        obj = stock_objs[figi]

        to_create_instances.append(
            models.Instrument(
                type=models.InstrumentType.STOCK,
                figi=obj.figi,
                name=obj.name,
                ticker=obj.ticker,
                currency=obj.currency,
                price_increment=obj.price_increment,
            )
        )

    await models.Instrument.bulk_create(to_create_instances)
    await models.Instrument.filter(figi__in=to_delete_ids).update(deleted_at=tz.now())

    if len(to_create_ids) > 0:
        logger.info('Stocks created: %s', len(to_create_ids))

    if len(to_delete_ids) > 0:
        logger.info('Stocks deleted: %s', len(to_delete_ids))


async def sync_day_candles(client: TinkoffClient) -> None:
    pass
