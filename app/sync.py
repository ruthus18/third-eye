# type: ignore
import asyncio
import functools
import logging
import signal

from aiocron import crontab
from tortoise import timezone as tz

from . import models
from .config import settings
from .schema import Currency
from .tinkoff import TinkoffClient

logger = logging.getLogger(__name__)


def sync_job(coro):
    def wrapper(coro):
        @functools.wraps(coro)
        async def wrapped(*args, **kwargs):
            logger.info('Running job: %s', coro.__name__)
            result = await coro(*args, **kwargs)

            logger.info('Job done: %s', coro.__name__)
            return result

        return wrapped

    coro.as_job = wrapper(coro)
    return coro


@sync_job
async def update_currencies(client: TinkoffClient) -> None:
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


@sync_job
async def update_stocks(client: TinkoffClient) -> None:
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


@sync_job
async def upload_day_candles(client: TinkoffClient) -> None:
    pass


async def run_scheduler() -> None:
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, stop_event.set)

    await models.init_db()
    tinkoff_client = TinkoffClient()

    cron_kwargs = {
        'args': (tinkoff_client, ), 'tz': settings.TIMEZONE
    }
    crontab('0 4 * * tue-sat', func=update_stocks.as_job, **cron_kwargs)
    crontab('10 4 * * tue-sat', func=upload_day_candles.as_job, **cron_kwargs)

    logger.info('Starting sync scheduler')
    try:
        await stop_event.wait()

    finally:
        logger.info('Shutting down')
        await models.close_db()
        await tinkoff_client.close()
