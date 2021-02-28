import argparse
import asyncio
import logging.config

from . import sync
from .config import settings

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['sync'])
    args = parser.parse_args()

    logging.config.dictConfig(settings.LOGGING)

    if args.command == 'sync':
        asyncio.run(sync.main())
