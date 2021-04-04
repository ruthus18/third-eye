import asyncio
import datetime as dt
import logging
import signal

from aiocron import crontab
from dateutil.relativedelta import relativedelta
from tortoise import timezone as tz

from . import models
from .config import settings
from .schema import CandleInterval, Currency
from .tinkoff import TinkoffClient

logger = logging.getLogger(__name__)


async def update_usd_stocks(client: TinkoffClient) -> None:
    logger.info('Updating USD stocks...')
    stocks = {
        obj.figi: obj for obj in await client.get_stocks() if obj.currency == Currency.USD
    }

    db_stock_ids = set(
        await models.Instrument
        .filter(type=models.InstrumentType.STOCK, currency=Currency.USD, deleted_at__isnull=True)
        .values_list('figi', flat=True)
    )
    stock_ids = set(stocks.keys())
    to_create_ids = stock_ids - db_stock_ids
    to_delete_ids = db_stock_ids - stock_ids

    to_create_instances = [
        models.Instrument(
            type=models.InstrumentType.STOCK,
            **stocks[figi].dict()
        )
        for figi in to_create_ids
    ]

    await models.Instrument.bulk_create(to_create_instances)
    await models.Instrument.filter(figi__in=to_delete_ids).update(deleted_at=tz.now())

    logger.info('Stocks created: %s, deleted: %s', len(to_create_ids), len(to_delete_ids))


async def init_day_candles(client: TinkoffClient) -> None:
    """Заполнение информации о дневных свечах с текущего дня по дату первого появления
    """
    logger.info('Init day candles for stocks...')
    sql = '''
        SELECT instrument.figi, instrument.ticker FROM instrument
            LEFT JOIN candle ON instrument.figi = candle.instrument_id
        WHERE instrument.delisted_at IS NOT NULL
        GROUP BY instrument.figi
        HAVING count(candle.id) = 0;
    '''
    instruments_to_upd = await models.db_query(sql)

    for figi, ticker in instruments_to_upd:
        end_dt = tz.now()
        start_dt = dt.datetime(end_dt.year, 1, 1, tzinfo=settings.TIMEZONE)

        candle_instances = []
        while start_dt.year >= 2015:
            candle_instances += [
                models.Candle(
                    instrument_id=figi,
                    interval=CandleInterval.D1,
                    **candle.dict(),
                )
                for candle in await client.get_candles(
                    figi, interval=CandleInterval.D1, start_dt=start_dt, end_dt=end_dt
                )
            ]
            end_dt = start_dt
            start_dt -= relativedelta(years=1)

        await models.Candle.bulk_create(candle_instances)
        logger.info('Uploaded %s candles for %s', len(candle_instances), ticker)

    # TODO: Fix counter when nothing to update
    logger.info('Day candles initialized for %s stocks', len(instruments_to_upd))


async def update_stocks_emerging_date(client: TinkoffClient) -> None:
    logger.info('Updating stocks emerging dates...')
    sql = '''
        SELECT candle.instrument_id, min(candle.time) FROM instrument
            LEFT JOIN candle ON instrument.figi = candle.instrument_id
        WHERE instrument.emerged_at IS NULL
        GROUP BY candle.instrument_id
        HAVING count(candle.id) > 0;
    '''
    instruments_to_upd = await models.db_query(sql)

    for figi, first_candle_time in instruments_to_upd:
        await models.Instrument.get(figi=figi).update(emerged_at=first_candle_time.date())  # type: ignore

    logger.info('Set stock emerging date for %s stocks', len(instruments_to_upd))


async def update_stocks_delisting_date(client: TinkoffClient) -> None:
    logger.info('Updating stocks delisting dates...')
    sql = '''
        SELECT candle.instrument_id, max(candle.time) FROM instrument
            LEFT JOIN candle ON instrument.figi = candle.instrument_id
        WHERE instrument.delisted_at IS NULL
        GROUP BY candle.instrument_id
        HAVING max(candle.time) < now() - '14 days' :: interval
            OR max(candle.time) IS NULl;
    '''
    instruments_to_upd = await models.db_query(sql)
    for figi, last_candle_time in instruments_to_upd:

        await models.Instrument.get(figi=figi).update(delisted_at=last_candle_time)  # type: ignore

    logger.info('Set stock delisting date for %s stocks', len(instruments_to_upd))


async def update_day_candles(client: TinkoffClient) -> None:
    dates_of_last_candle = {
        figi: last_time
        for figi, last_time in await models.db_query(
            'SELECT instrument_id, max(time) FROM candle GROUP BY instrument_id;'
        )
    }
    stocks = await models.Instrument.filter(
        type=models.InstrumentType.STOCK,
        deleted_at__isnull=True,
        delisted_at__isnull=True,
    ).order_by('ticker')
    now = tz.now()

    for stock in stocks:
        last_date_candle = dates_of_last_candle.get(stock.figi)
        if not last_date_candle or last_date_candle.date() == now.date():
            continue

        start_dt = last_date_candle
        end_dt = last_date_candle + relativedelta(years=1)
        candle_instances = []

        while start_dt.date() < now.date():
            candle_instances += [
                models.Candle(
                    instrument=stock,
                    interval=CandleInterval.D1,
                    **candle.dict(),
                )
                for candle in await client.get_candles(
                    stock.figi, interval=CandleInterval.D1, start_dt=start_dt, end_dt=end_dt
                )
            ]

            start_dt = end_dt
            end_dt += relativedelta(years=1)

        await models.Candle.bulk_create(candle_instances)
        logger.info('Uploaded %s candles for %s', len(candle_instances), stock.ticker)

    if len(stocks) > 0:
        logger.info('Init candles for %s stocks', len(stocks))


async def main() -> None:
    await models.init_db()
    client = TinkoffClient()

    await update_usd_stocks(client)

    await init_day_candles(client)
    await update_stocks_emerging_date(client)

    await update_day_candles(client)
    await update_stocks_delisting_date(client)

    logger.info('Sync done')

    await client.close()
    await models.close_db()


async def run_scheduler() -> None:
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, stop_event.set)

    crontab('0 4 * * tue-sat', func=main, tz=settings.TIMEZONE)

    logger.info('Starting sync scheduler')
    try:
        await stop_event.wait()

    finally:
        logger.info('Shutting down')
