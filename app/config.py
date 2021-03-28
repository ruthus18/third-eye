import logging
from typing import Any, Dict, Literal, Optional

import httpx
import pytz
from pydantic import AnyUrl, BaseSettings, Field, SecretStr, root_validator
from pytz.tzinfo import DstTzInfo


class Settings(BaseSettings):
    ENVIRONMENT: Literal['local', 'prod'] = 'local'

    TINKOFF_HTTP_URL: httpx.URL = httpx.URL('https://api-invest.tinkoff.ru/openapi/')
    TINKOFF_WS_URL: AnyUrl = Field('wss://api-invest.tinkoff.ru/openapi/md/v1/md-openapi/ws')
    TINKOFF_TOKEN: SecretStr = SecretStr('')

    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_USER: str = 'third_eye'
    DB_PASSWORD: str = 'third_eye'
    DB_NAME: str = 'third_eye'

    TORTOISE_ORM: Dict[str, Any] = {}

    TZ_NAME: str = 'Asia/Yekaterinburg'
    TIMEZONE: Optional[DstTzInfo] = None

    LOGGING_LEVEL: Literal['DEBUG', 'INFO', 'ERROR'] = Field('INFO')
    LOGGING_FORMAT: str = '[%(asctime)s] %(levelname)s %(name)s: %(message)s'
    LOGGING: Dict[str, Any] = {}

    @root_validator
    @classmethod
    def post_init(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        values['TORTOISE_ORM'].update({
            'connections': {
                'default': {
                    'engine': 'tortoise.backends.asyncpg',
                    'credentials': {
                        'host': values['DB_HOST'],
                        'port': values['DB_PORT'],
                        'user': values['DB_USER'],
                        'password': values['DB_PASSWORD'],
                        'database': values['DB_NAME'],
                    },
                },
            },
            'apps': {
                'models': {
                    'models': ['app.models', 'aerich.models'],
                },
            },
            'use_tz': True,
            'timezone': 'Asia/Yekaterinburg'
        })

        values['LOGGING'].update({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': values['LOGGING_FORMAT'],
                },
            },
            'handlers': {
                'stdout': {
                    'level': values['LOGGING_LEVEL'],
                    'class': 'logging.StreamHandler',
                    'formatter': 'default',
                },
            },
            'loggers': {
                '': {
                    'handlers': ['stdout'],
                    'level': values['LOGGING_LEVEL'],
                },
                'tortoise': {
                    'level': logging.ERROR,
                },
            },
        })

        if not values['TZ_NAME']:
            raise RuntimeError('Timezone name not specified')

        values['TIMEZONE'] = pytz.timezone(values['TZ_NAME'])

        return values

    class Config:
        env_file = '.env'
        allow_mutation = False


settings = Settings()

TORTOISE_ORM = settings.TORTOISE_ORM
