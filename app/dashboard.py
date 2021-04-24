# type: ignore
import asyncio
import datetime as dt
import logging
from decimal import Decimal
from enum import Enum
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from cachetools.func import ttl_cache

from app.tinkoff import TinkoffClient

from . import graphs, models, schema
from .support_resistance import SupportResistanceSearch
from .utils import localize_dt

logger = logging.getLogger(__name__)

EMPTY_CHOICE = '-----'

loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()


tinkoff_client = TinkoffClient()


def _await(coro):
    return loop.run_until_complete(coro)


@st.cache
def init():
    _await(models.init_db())
    logger.info('DB initialized')


class Page:
    @classmethod
    def init(cls, *args, **kwargs):
        raise NotImplementedError('You should implement initialization with Streamlit caching (`st.cache` decorator)')

    def show(self):
        raise NotImplementedError('You should implement page drawing logic')


class MainPage(Page):
    @classmethod
    def init(cls):
        return cls()

    def show(self):
        st.write('Welcome!')


class StocksViewerPage(Page):

    def __init__(self, default_start_date: dt.datetime, default_end_date: dt.datetime):
        self.default_candle_start_date = default_start_date
        self.default_candle_end_date = default_end_date

        self.default_sr_start_date = default_start_date
        self.default_sr_end_date = default_end_date

        self.stocks_choices = self._get_stocks_choices()

        self.candle_start_date = None
        self.candle_end_date = None

        self.show_sr = None
        self.sr_start_date = None
        self.sr_end_date = None
        self.sr_significance_threshold = None

        self.ticker = None
        self.show_hover = None

        self._graph = None

    @classmethod
    @st.cache(allow_output_mutation=True)
    def init(
        cls,
        default_start_date: dt.datetime = dt.date(2021, 1, 1),
        default_end_date: dt.datetime = dt.date.today(),
    ) -> 'StocksViewerPage':
        return cls(default_start_date, default_end_date)

    @staticmethod
    @st.cache
    def _get_stocks_choices():
        stocks = _await(
            models.Instrument
            .filter(delisted_at__isnull=True, deleted_at__isnull=True)
            .order_by('ticker')
            .values_list('ticker', 'name')
        )
        return {ticker: name for ticker, name in stocks}

    def format_stocks_selectbox(self, ticker: str) -> str:
        if ticker == EMPTY_CHOICE:
            return ticker

        return f"{ticker} ({self.stocks_choices[ticker]})"

    @staticmethod
    @ttl_cache(ttl=600)
    def get_candles_df(
        ticker: str,
        start_date: dt.date,
        end_date: dt.date,
        timeframe: schema.CandleInterval,
    ):
        stock = _await(models.Instrument.get(ticker=ticker))
        start_dt = localize_dt(dt.datetime.combine(start_date, dt.time()))
        end_dt = localize_dt(dt.datetime.combine(end_date, dt.time(23, 59)))

        if timeframe == schema.CandleInterval.D1:
            candles_data = _await(
                models.Candle.filter(
                    instrument=stock,
                    interval=schema.CandleInterval.D1,
                )
                .filter(time__gte=start_dt, time__lte=end_dt)
                .values('open', 'close', 'high', 'low', 'volume', 'time')
            )

        else:
            candles_data = _await(tinkoff_client.get_candles(
                figi=stock.figi, interval=timeframe, start_dt=start_dt, end_dt=end_dt
            ))
            candles_data = (o.dict() for o in candles_data)

        return pd.DataFrame.from_dict(candles_data)

    @classmethod
    @st.cache(allow_output_mutation=True)
    def get_candles_graph(
        cls,
        ticker: str,
        candle_start_date: dt.date,
        candle_end_date: dt.date,
        candle_timeframe: schema.CandleInterval,
        sr_start_date: Optional[dt.date] = None,
        sr_end_date: Optional[dt.date] = None,
        sr_significance_threshold: Optional[float] = None,
    ):
        candles_df = cls.get_candles_df(ticker, candle_start_date, candle_end_date, candle_timeframe)
        graph = graphs.get_candles_graph(ticker, candles_df)

        if sr_start_date and sr_end_date:
            sr_candles_df = pd.DataFrame.from_dict(_await(
                models.Candle.filter(
                    instrument__ticker=ticker,
                    interval=schema.CandleInterval.D1,
                )
                .filter(
                    time__gte=localize_dt(dt.datetime.combine(sr_start_date, dt.time())),
                    time__lte=localize_dt(dt.datetime.combine(sr_end_date, dt.time(23, 59))),
                )
                .values('open', 'close', 'high', 'low', 'volume', 'time')
            ))
            sr_levels = SupportResistanceSearch(sr_candles_df).find_levels(Decimal(sr_significance_threshold))
            for _, level in sr_levels.iterrows():
                graphs.draw_line(
                    graph=graph,
                    x0=min(candles_df.time),
                    x1=max(candles_df.time),
                    y0=level['price'],
                    y1=level['price'],
                    opacity=level['significance']
                )

        return graph

    @staticmethod
    @st.cache
    def update_graph_hover(graph: go.Figure, show_hover: bool):
        graphs.update_graph_hover(graph, show_hover)

    def show_sidebar(self):
        st.sidebar.text('Candles')
        self.ticker = st.sidebar.selectbox(
            'Ticker',
            [EMPTY_CHOICE, *self.stocks_choices.keys()],
            format_func=self.format_stocks_selectbox
        )

        self.candle_start_date = st.sidebar.date_input('Start Date', value=self.default_candle_start_date)
        self.candle_end_date = st.sidebar.date_input('End Date', value=self.default_candle_end_date)
        self.candle_timeframe = st.sidebar.selectbox(
            'Timeframe',
            list(ch.value for ch in schema.CandleInterval),
            list(ch.value for ch in schema.CandleInterval).index('day')
        )

        self.show_hover = st.sidebar.checkbox('Show Hover', value=False)

        st.sidebar.markdown('---')
        st.sidebar.text('Support/Resistance Levels')
        self.show_sr_levels = st.sidebar.checkbox('Show Levels', value=False)
        self.sr_start_date = st.sidebar.date_input('S/R Start Date', value=self.default_sr_start_date)
        self.sr_end_date = st.sidebar.date_input('S/R End Date', value=self.default_sr_end_date)
        self.sr_significance_threshold = st.sidebar.number_input('Significnce Threshold', value=0.25)

    def show(self):
        self.show_sidebar()

        if self.ticker != EMPTY_CHOICE:
            st.title(self.stocks_choices[self.ticker])

            candle_kwargs = {
                'ticker': self.ticker,
                'candle_start_date': self.candle_start_date,
                'candle_end_date': self.candle_end_date,
                'candle_timeframe': self.candle_timeframe,
            }
            if self.show_sr_levels:
                candle_kwargs = {
                    **candle_kwargs,
                    'sr_start_date': self.sr_start_date,
                    'sr_end_date': self.sr_end_date,
                    'sr_significance_threshold': self.sr_significance_threshold
                }

            graph = self.get_candles_graph(**candle_kwargs)
            self.update_graph_hover(graph, self.show_hover)

            st.plotly_chart(graph, use_container_width=True, config={'displayModeBar': False})


class MenuChoices(str, Enum):
    STOCKS_VIEWER = 'Stocks Viewer'
    MAIN_PAGE = 'Main Page'

    def __str__(self):
        return self.value

    @property
    def page_cls(self):
        return {
            self.MAIN_PAGE: MainPage,
            self.STOCKS_VIEWER: StocksViewerPage,
        }[self]


# TODO: Find a way to add shutdown logic
def main():
    init()

    selected_page = st.sidebar.selectbox('Page', list(MenuChoices))
    st.sidebar.markdown('---')

    pages = {}

    if selected_page not in pages:
        pages[selected_page] = selected_page.page_cls.init()

    pages[selected_page].show()
