import asyncio
import datetime as dt
import logging
from typing import Any, Dict, List, Literal, Optional

import httpx
from dateutil.relativedelta import relativedelta

from .config import settings
from .schema import BalanceItem, Candle, Instrument, Timeframe
from .utils import localize_dt

logger = logging.getLogger(__name__)


USD_FIGI = 'BBG0013HGFT4'


class TinkoffAPIError(Exception):
    pass


class TinkoffClient:
    """Client for making HTTP requests to Invest API

    Documentation: https://tinkoffcreditsystems.github.io/invest-openapi/swagger-ui
    """
    CANDLE_REQUEST_BATCH = {
        Timeframe.M1: relativedelta(days=1),
        Timeframe.M5: relativedelta(days=1),
        Timeframe.M10: relativedelta(days=1),
        Timeframe.M30: relativedelta(days=1),
        Timeframe.H1: relativedelta(weeks=1),
        Timeframe.D1: relativedelta(years=1),
        Timeframe.D7: relativedelta(years=2),
        Timeframe.D30: relativedelta(years=10),
    }

    def __init__(self, token: str = ''):
        token = token or settings.TINKOFF_TOKEN.get_secret_value()
        if not token:
            raise RuntimeError('No token specified for Tinkoff client')

        self._client = httpx.AsyncClient(
            headers={'Authorization': f'Bearer {token}'}
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: Literal['GET', 'POST'],
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retries_on_ratelimit: int = 2,
    ) -> Dict[str, Any]:

        url = settings.TINKOFF_HTTP_URL.join(endpoint)
        response = await self._client.request(
            method=method,
            url=url,
            json=json_data or {},
            params=params or {},
        )

        if response.status_code == 429:
            if retries_on_ratelimit <= 0:
                raise TinkoffAPIError('Rate limit for requests exceed')

            logger.info('API requests limit reached. Waiting 1 min...')
            await asyncio.sleep(60)
            return await self._request(method, endpoint, json_data, params, retries_on_ratelimit - 1)

        response_data = response.json()
        payload: Dict[str, Any] = response_data['payload']

        if response_data['status'] == 'Error':
            raise TinkoffAPIError(f"{payload['code']}: {payload['message']}")

        return payload

    async def get_balance(self) -> List[BalanceItem]:
        portfolio_data = await self._request('GET', 'portfolio/currencies')
        return [BalanceItem(**obj) for obj in portfolio_data['currencies']]

    # async def get_portfolio(self) -> List[PortfolioItem]:
    #     portfolio_data = await self._request('GET', 'portfolio')
    #     return [
    #         PortfolioItem(
    #             instrument=Instrument(
    #                 name=item['name'],
    #                 ticker=item['ticker'],
    #                 figi=item['figi'],
    #                 currency=item['averagePositionPrice']['currency']
    #             ),
    #             lots=item['lots'],
    #         )
    #         for item in portfolio_data['positions']
    #         if item['figi'] != USD_FIGI
    #     ]

    async def _get_instruments(self, kind: Literal['stocks', 'bonds', 'currencies']) -> List[Instrument]:
        response = await self._request('GET', f'market/{kind}')
        return [
            Instrument(**obj) for obj in response['instruments']
            if 'minPriceIncrement' in obj
        ]

    async def get_stocks(self) -> List[Instrument]:
        return await self._get_instruments('stocks')

    async def get_bonds(self) -> List[Instrument]:
        return await self._get_instruments('bonds')

    async def get_currencies(self) -> List[Instrument]:
        return await self._get_instruments('currencies')

    async def get_candles(
        self, figi: str, timeframe: Timeframe, start_dt: dt.datetime, end_dt: dt.datetime
    ) -> List[Candle]:
        """Get historic candles for selected instrument, period and timeframe.
        """
        def make_tz_aware(datetime: dt.datetime) -> str:
            if datetime.tzinfo:
                return datetime.isoformat()

            return localize_dt(datetime).isoformat()

        if end_dt < start_dt:
            raise ValueError('End period should be greater than start period')

        batch_size = self.CANDLE_REQUEST_BATCH[timeframe]
        start, end = start_dt, end_dt
        if (start + batch_size) < end:
            end = start + batch_size

        candles = []
        while True:
            response = await self._request('GET', 'market/candles', params={
                'figi': figi,
                'from': make_tz_aware(start),
                'to': make_tz_aware(end),
                'interval': timeframe,
            })
            candles.extend([Candle(**obj) for obj in response['candles']])

            if end == end_dt:
                break

            start = end
            end += batch_size
            if end > end_dt:
                end = end_dt

        return candles
