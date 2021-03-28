# type: ignore
import asyncio
import logging
from enum import Enum

import streamlit as st

from . import models

logger = logging.getLogger(__name__)

loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()


class MenuChoices(str, Enum):
    MAIN_PAGE = 'Main Page'
    STOCKS_VIEWER = 'Stocks Viewer'
    TRADING_SUMMARY = 'Trading Summary'

    def __str__(self):
        return self.value


def _await(coro):
    return loop.run_until_complete(coro)


@st.cache
def init():
    _await(models.init_db())
    logger.info('DB initialized')


def stocks_viewer():

    @st.cache
    def get_stock_tickers():
        return _await(
            models.Instrument
            .filter(delisted_at__isnull=True, deleted_at__isnull=True)
            .values_list('ticker', flat=True)
        )

    st.sidebar.selectbox('Ticker', get_stock_tickers())


# TODO: Find a way to add shutdown logic
def main():
    init()

    page = st.sidebar.selectbox('Navigation', list(MenuChoices))
    st.sidebar.markdown('---')

    st.title(page)
    if page == MenuChoices.MAIN_PAGE:
        st.write('Welcome!')

    elif page == MenuChoices.STOCKS_VIEWER:
        stocks_viewer()

    elif page == MenuChoices.TRADING_SUMMARY:
        pass

    else:
        raise RuntimeError('Unknown page')
