"""Plotly chart builders with a consistent dark theme."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

UP = "#26A69A"
DOWN = "#EF5350"
ACCENT = "#4C9AFF"
BENCH = "#B0B7C3"
SERIES = ["#4C9AFF", "#F5A623", "#26A69A", "#E57373", "#BA68C8", "#4DD0E1", "#AED581", "#FFB74D"]

_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=30, b=10),
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    font=dict(size=12),
)


def price_chart(df: pd.DataFrame, kind: str = "Line", show_ma: bool = True, currency: str | None = None,
                use_adjusted: bool = False) -> go.Figure:
    """Candlestick or line price chart with a volume subplot and optional 50/200 moving averages."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.78, 0.22])
    close_col = "Adj Close" if use_adjusted and "Adj Close" in df and df["Adj Close"].notna().any() else "Close"
    if kind == "Candlestick" and {"Open", "High", "Low", "Close"} <= set(df.columns):
        fig.add_trace(
            go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                           increasing_line_color=UP, decreasing_line_color=DOWN, name="OHLC"),
            row=1, col=1,
        )
    else:
        first, last = df[close_col].dropna().iloc[[0, -1]] if df[close_col].notna().sum() >= 2 else (0, 0)
        color = UP if last >= first else DOWN
        fig.add_trace(
            go.Scatter(x=df.index, y=df[close_col], mode="lines", name=close_col, line=dict(color=color, width=2)),
            row=1, col=1,
        )
    if show_ma and len(df) >= 50:
        for window, color in ((50, "#F5A623"), (200, "#BA68C8")):
            if len(df) >= window:
                fig.add_trace(go.Scatter(x=df.index, y=df[close_col].rolling(window).mean(), mode="lines",
                                         name=f"{window}-period MA", line=dict(color=color, width=1.2)), row=1, col=1)
    if "Volume" in df:
        colors = [UP if c >= o else DOWN for o, c in zip(df.get("Open", df[close_col]), df[close_col])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors, name="Volume", opacity=0.6), row=2, col=1)
    fig.update_layout(**_LAYOUT, height=520, xaxis_rangeslider_visible=False, showlegend=True)
    fig.update_yaxes(title_text=f"Price{f' ({currency})' if currency else ''}", row=1, col=1, side="right")
    fig.update_yaxes(title_text="Volume", row=2, col=1, side="right")
    return fig


def sparkline(df: pd.DataFrame, height: int = 140) -> go.Figure:
    s = df["Close"].dropna()
    color = UP if len(s) > 1 and s.iloc[-1] >= s.iloc[0] else DOWN
    fig = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(color=color, width=2), hovertemplate="%{x|%b %d, %Y}: %{y:,.2f}<extra></extra>"))
    fig.update_layout(**{**_LAYOUT, "margin": dict(l=0, r=0, t=0, b=0)}, height=height, showlegend=False)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def statement_chart(series: dict[str, pd.Series], labels: dict[str, str], chart_type: str = "Bar",
                    unit_label: str = "", divisor: float = 1.0) -> go.Figure:
    """series: key -> values indexed by period (any order); plotted oldest -> newest."""
    fig = go.Figure()
    for i, (key, s) in enumerate(series.items()):
        s = s.sort_index()
        x = [p.strftime("%Y-%m-%d") for p in s.index]
        y = s.values / divisor
        name = labels.get(key, key)
        color = SERIES[i % len(SERIES)]
        if chart_type == "Line":
            fig.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines+markers", line=dict(color=color, width=2)))
        else:
            fig.add_trace(go.Bar(x=x, y=y, name=name, marker_color=color))
    fig.update_layout(**_LAYOUT, height=380, barmode="group")
    fig.update_xaxes(type="category", title_text="Period end")
    fig.update_yaxes(title_text=unit_label)
    return fig


def performance_chart(rows: list[dict], symbol: str, benchmark: str) -> go.Figure:
    periods = [r["period"] for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=periods, y=[None if r["stock_return"] is None else r["stock_return"] * 100 for r in rows],
                         name=symbol, marker_color=ACCENT, texttemplate="%{y:.1f}%", textposition="outside"))
    fig.add_trace(go.Bar(x=periods, y=[None if r["benchmark_return"] is None else r["benchmark_return"] * 100 for r in rows],
                         name=benchmark, marker_color=BENCH, texttemplate="%{y:.1f}%", textposition="outside"))
    fig.update_layout(**_LAYOUT, height=300, barmode="group")
    fig.update_yaxes(title_text="Total return (%)", ticksuffix="%")
    return fig


def bar_series(s: pd.Series, title: str, color: str = ACCENT, height: int = 260) -> go.Figure:
    fig = go.Figure(go.Bar(x=s.index, y=s.values, marker_color=color, name=title))
    fig.update_layout(**_LAYOUT, height=height, title=dict(text=title, font=dict(size=13)), showlegend=False)
    return fig


def ownership_donut(major: dict) -> go.Figure | None:
    insiders = major.get("insidersPercentHeld")
    institutions = major.get("institutionsPercentHeld")
    if insiders is None or institutions is None:  # don't plot an unavailable share as zero
        return None
    other = max(0.0, 1 - insiders - institutions)
    fig = go.Figure(go.Pie(labels=["Insiders", "Institutions", "Other / Retail"], values=[insiders, institutions, other],
                           hole=0.6, marker=dict(colors=["#F5A623", ACCENT, "#5C6370"]), sort=False,
                           texttemplate="%{percent:.1%}"))
    fig.update_layout(**{**_LAYOUT, "hovermode": "closest"}, height=280, showlegend=True)
    return fig
