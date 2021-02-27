import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional

import httpx

from .config import settings
from .schema import Instrument

logger = logging.getLogger(__name__)


class TinkoffAPIError(Exception):
    pass


class TinkoffClient:
    """Client for making HTTP requests to Invest API

    Documentation: https://tinkoffcreditsystems.github.io/invest-openapi/swagger-ui
    """

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

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TinkoffAPIError(str(e))

        response_data: Dict[str, Any] = response.json()['payload']
        if response_data['status'] == 'Error':
            payload = response_data['payload']

            raise TinkoffAPIError(f"{payload['code']}: {payload['message']}")

        return response_data

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
