# type: ignore
import asyncio
import datetime as dt
import logging
from enum import Enum

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import graphs, models, schema
from .config import settings

logger = logging.getLogger(__name__)


loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()

EMPTY_CHOICE = '-----'


class MenuChoices(str, Enum):
    STOCKS_VIEWER = 'Stocks Viewer'
    MAIN_PAGE = 'Main Page'

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
    def get_stocks_data():
        stocks = _await(
            models.Instrument
            .filter(delisted_at__isnull=True, deleted_at__isnull=True)
            .order_by('ticker')
            .values_list('ticker', 'name')
        )
        return {ticker: name for ticker, name in stocks}

    @st.cache(allow_output_mutation=True)
    def get_candles_graph(ticker: str, start_time: dt.date, end_time: dt.date, support_resistance: bool = False):
        candles_data = _await(
            models.Candle.filter(
                instrument__ticker=ticker,
                time__gte=settings.TIMEZONE.localize(dt.datetime.combine(start_time, dt.time())),
                time__lte=settings.TIMEZONE.localize(dt.datetime.combine(end_time, dt.time(23, 59))),
                interval=schema.CandleInterval.D1,
            ).values()
        )
        return graphs.get_candles_graph(ticker, pd.DataFrame.from_dict(candles_data))

    @st.cache
    def update_graph_hover(graph: go.Figure, show_hover: bool):
        graphs.update_graph_hover(graph, show_hover)

    def format_selectbox(ticker: str):
        if ticker == EMPTY_CHOICE:
            return ticker

        return f"{ticker} ({stocks[ticker]})"

    stocks = get_stocks_data()

    ticker = st.sidebar.selectbox(
        'Ticker',
        [EMPTY_CHOICE, *stocks.keys()],
        format_func=format_selectbox
    )
    start_time = st.sidebar.date_input('Start Time', value=dt.date(2021, 1, 1))
    end_time = st.sidebar.date_input('End Time', value=dt.date.today())

    show_hover = st.sidebar.checkbox('Show Hover', value=False)

    if ticker != EMPTY_CHOICE:
        graph = get_candles_graph(ticker, start_time, end_time)
        update_graph_hover(graph, show_hover)

        st.plotly_chart(graph, use_container_width=True, config={'displayModeBar': False})


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

    else:
        raise RuntimeError('Unknown page')
