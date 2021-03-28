import argparse
import asyncio
import logging
import logging.config
import os

from . import sync
from .config import settings

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['sync', 'dashboard'])
    args = parser.parse_args()

    logging.config.dictConfig(settings.LOGGING)

    if args.command == 'sync':
        asyncio.run(sync.run_scheduler())

    elif args.command == 'dashboard':
        streamlit_args = [
            'streamlit run run_dashboard.py',
            '--global.sharingMode off',
            '--server.port 8000',
            f'--logger.messageFormat "{settings.LOGGING_FORMAT}"',
        ]

        if settings.ENVIRONMENT == 'prod':
            streamlit_args.append('--server.headless true')
            streamlit_args.append('--global.disableWatchdogWarning true')
            streamlit_args.append('--global.fileWatcherType none')

        os.system(' '.join(streamlit_args))
