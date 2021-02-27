import contextlib
import datetime as dt
from typing import Any, Dict

import httpx
import pytz
from pydantic import AnyUrl, BaseSettings, Field, SecretStr, root_validator


class Settings(BaseSettings):
    TINKOFF_HTTP_URL: httpx.URL = httpx.URL('https://api-invest.tinkoff.ru/openapi/')
    TINKOFF_WS_URL: AnyUrl = Field('wss://api-invest.tinkoff.ru/openapi/md/v1/md-openapi/ws')

    TINKOFF_TOKEN: SecretStr = SecretStr('')

    TZ_NAME: str = 'Asia/Yekaterinburg'
    TIMEZONE: dt.tzinfo = None

    class Config:
        env_file = '.env'
        allow_mutation = False

    @root_validator
    @classmethod
    def post_init(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        with contextlib.suppress(pytz.UnknownTimeZoneError):
            values['TIMEZONE'] = pytz.timezone(values['TZ_NAME'])

        return values


settings = Settings()
