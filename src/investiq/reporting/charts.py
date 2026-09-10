"""Plotly chart generation for the InvestIQ research report.

All chart functions accept a pandas DataFrame and return Plotly HTML div
strings.  Each chart handles null data gracefully.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

_CHART_CONFIG = {"displayModeBar": False, "responsive": True}

_TEMPLATE = "plotly_white"

_COLOR_ROE = "#2563EB"
_COLOR_ROA = "#7C3AED"
_COLOR_NIM = "#059669"
_COLOR_CASA = "#D97706"
_COLOR_COST_INCOME = "#DC2626"
_COLOR_GROSS_NPA = "#EF4444"
_COLOR_NET_NPA = "#F97316"
_COLOR_EPS = "#2563EB"
_COLOR_BVPS = "#7C3AED"
_COLOR_CREDIT_COST = "#DC2626"


def _df_or_none(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df


def _sort_fiscal(df: pd.DataFrame, col: str = "fiscal_year") -> pd.DataFrame:
    if col not in df.columns:
        return df
    return df.sort_values(col).reset_index(drop=True)


def _has_columns(df: pd.DataFrame, *cols: str) -> bool:
    for c in cols:
        if c not in df.columns or df[c].isnull().all():
            return False
    return True

def roe_roa_chart(df: pd.DataFrame | None) -> str:
    """ROE & ROA dual-axis/line chart."""
    df = _sort_fiscal(_df_or_none(df))
    if not _has_columns(df, "fiscal_year", "roe", "roa"):
        return "<p class='chart-unavailable'>ROE/ROA data unavailable</p>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["roe"],
        mode="lines+markers", name="ROE (%)",
        line=dict(color=_COLOR_ROE, width=3),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["roa"],
        mode="lines+markers", name="ROA (%)",
        line=dict(color=_COLOR_ROA, width=3),
        marker=dict(size=8),
    ))
    fig.update_layout(
        title=dict(text="ROE & ROA Trend", x=0, xanchor="left", font=dict(size=14)),
        template=_TEMPLATE,
        xaxis_title="Fiscal Year", yaxis_title="Percentage (%)",
        hovermode="x unified", margin=dict(l=40, r=20, t=60, b=80),
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    return _chart_html(fig)


def nim_chart(df: pd.DataFrame | None) -> str:
    df = _sort_fiscal(_df_or_none(df))
    if not _has_columns(df, "fiscal_year", "nim"):
        return "<p class='chart-unavailable'>NIM data unavailable</p>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["nim"],
        mode="lines+markers", name="NIM (%)",
        line=dict(color=_COLOR_NIM, width=3),
        marker=dict(size=8),
        fill="tozeroy", fillcolor="rgba(5,150,105,0.12)",
    ))
    fig.update_layout(
        title="Net Interest Margin (NIM) Trend", template=_TEMPLATE,
        xaxis_title="Fiscal Year", yaxis_title="NIM (%)",
        hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40),
    )
    return _chart_html(fig)


def casa_chart(df: pd.DataFrame | None) -> str:
    df = _sort_fiscal(_df_or_none(df))
    if not _has_columns(df, "fiscal_year", "casa_ratio"):
        return "<p class='chart-unavailable'>CASA ratio data unavailable</p>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["casa_ratio"],
        mode="lines+markers", name="CASA Ratio (%)",
        line=dict(color=_COLOR_CASA, width=3),
        marker=dict(size=8),
        fill="tozeroy", fillcolor="rgba(217,119,6,0.12)",
    ))
    fig.update_layout(
        title="CASA Ratio Trend", template=_TEMPLATE,
        xaxis_title="Fiscal Year", yaxis_title="CASA Ratio (%)",
        hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40),
    )
    return _chart_html(fig)


def cost_to_income_chart(df: pd.DataFrame | None) -> str:
    df = _sort_fiscal(_df_or_none(df))
    if not _has_columns(df, "fiscal_year", "cost_to_income"):
        return "<p class='chart-unavailable'>Cost-to-Income data unavailable</p>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["cost_to_income"],
        mode="lines+markers", name="Cost-to-Income (%)",
        line=dict(color=_COLOR_COST_INCOME, width=3),
        marker=dict(size=8),
    ))
    fig.update_layout(
        title="Cost-to-Income Ratio Trend", template=_TEMPLATE,
        xaxis_title="Fiscal Year", yaxis_title="Cost-to-Income (%)",
        hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40),
    )
    return _chart_html(fig)


def npa_chart(df: pd.DataFrame | None) -> str:
    df = _sort_fiscal(_df_or_none(df))
    if not _has_columns(df, "fiscal_year", "gross_npa_ratio", "net_npa_ratio"):
        return "<p class='chart-unavailable'>NPA data unavailable</p>"
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["fiscal_year"], y=df["gross_npa_ratio"],
        name="Gross NPA (%)", marker_color=_COLOR_GROSS_NPA,
    ))
    fig.add_trace(go.Bar(
        x=df["fiscal_year"], y=df["net_npa_ratio"],
        name="Net NPA (%)", marker_color=_COLOR_NET_NPA,
    ))
    fig.update_layout(
        title=dict(text="Gross NPA vs Net NPA", x=0, xanchor="left", font=dict(size=14)),
        template=_TEMPLATE,
        xaxis_title="Fiscal Year", yaxis_title="NPA Ratio (%)",
        barmode="group", hovermode="x unified",
        margin=dict(l=40, r=20, t=60, b=80),
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    return _chart_html(fig)


def eps_bvps_chart(df: pd.DataFrame | None) -> str:
    df = _sort_fiscal(_df_or_none(df))
    if not _has_columns(df, "fiscal_year", "eps", "bvps"):
        return "<p class='chart-unavailable'>EPS/BVPS data unavailable</p>"
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["eps"],
        mode="lines+markers", name="EPS (₹)",
        line=dict(color=_COLOR_EPS, width=3),
        marker=dict(size=8),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["bvps"],
        mode="lines+markers", name="BVPS (₹)",
        line=dict(color=_COLOR_BVPS, width=3),
        marker=dict(size=8),
    ), secondary_y=True)
    fig.update_layout(
        title=dict(text="EPS & Book Value Per Share", x=0, xanchor="left", font=dict(size=14)),
        template=_TEMPLATE,
        hovermode="x unified", margin=dict(l=40, r=20, t=60, b=80),
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
    )
    fig.update_xaxes(title_text="Fiscal Year")
    fig.update_yaxes(title_text="EPS (₹)", secondary_y=False)
    fig.update_yaxes(title_text="BVPS (₹)", secondary_y=True)
    return _chart_html(fig)


def credit_cost_chart(df: pd.DataFrame | None) -> str:
    df = _sort_fiscal(_df_or_none(df))
    if not _has_columns(df, "fiscal_year", "credit_cost"):
        return "<p class='chart-unavailable'>Credit cost data unavailable</p>"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["fiscal_year"], y=df["credit_cost"],
        mode="lines+markers", name="Credit Cost (%)",
        line=dict(color=_COLOR_CREDIT_COST, width=3),
        marker=dict(size=8),
        fill="tozeroy", fillcolor="rgba(220,38,38,0.12)",
    ))
    fig.update_layout(
        title="Credit Cost Trend", template=_TEMPLATE,
        xaxis_title="Fiscal Year", yaxis_title="Credit Cost (%)",
        hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40),
    )
    return _chart_html(fig)


ALL_METRIC_CHARTS = [
    roe_roa_chart,
    nim_chart,
    casa_chart,
    cost_to_income_chart,
    npa_chart,
    eps_bvps_chart,
    credit_cost_chart,
]


def render_all_metric_charts(df: pd.DataFrame | None) -> list[str]:
    return [fn(df) for fn in ALL_METRIC_CHARTS]


def _chart_html(fig: go.Figure) -> str:
    return fig.to_html(include_plotlyjs="cdn", full_html=False, config=_CHART_CONFIG)