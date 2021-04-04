from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def get_candles_graph(ticker: str, candles_data: List[Dict[str, Any]], show_hover: bool = False) -> go.Figure:
    df = pd.DataFrame.from_dict(candles_data)
    fig = make_subplots(rows=2, cols=1, row_heights=[0.8, 0.15], vertical_spacing=0.05)

    fig.add_trace(
        go.Candlestick(
            x=df.time,
            open=df.open,
            high=df.high,
            low=df.low,
            close=df.close,
            name=ticker,
            increasing_line_color='#2d9462',
            increasing_fillcolor='#2d9462',
            decreasing_line_color='#f62f47',
            decreasing_fillcolor='#f62f47',
            line={'width': 1},
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df.time,
            y=df.volume,
            marker_color='#7658e0',
            name='Volume',
        ),
        row=2, col=1,
    )
    fig.update_layout(
        {'plot_bgcolor': '#ffffff', 'paper_bgcolor': '#ffffff', 'legend_orientation': "h"},
        legend=dict(y=1, x=0),
        height=700,
        dragmode='pan',
        hovermode='x unified',
        margin=dict(b=20, t=0, l=0, r=40)
    )

    axes_config = {
        'zeroline': False,
        'showgrid': False,
        'showline': False,
        'showspikes': True,
        'spikemode': 'across',
        'spikedash': 'solid',
        'spikesnap': 'cursor',
        'spikecolor': '#aaaaaa',
        'spikethickness': 1,
    }
    fig.update_yaxes(**axes_config)
    fig.update_xaxes(rangeslider_visible=False, **axes_config)

    fig.update_traces(xaxis='x', hoverinfo='x+y')
    return fig


def update_graph_hover(graph: go.Figure, show_hover: bool) -> None:
    graph.update_layout(hoverdistance=1 if show_hover else 0)
