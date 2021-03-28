import logging.config

from app.config import settings
from app.dashboard import main  # type: ignore

logging.config.dictConfig(settings.LOGGING)

main()
