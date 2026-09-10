"""Report builder — transforms ReportData into an interactive HTML report.

Orchestrates the data → charts → template pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from investiq.reporting.charts import render_all_metric_charts
from investiq.reporting.data import ReportData, ReportDataFetcher

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=False,
)

KNOWN_THESIS_LABELS: dict[str, str] = {
    "STRENGTH": "Key Strength", "CONCERN": "Key Concern",
    "GROWTH_DRIVER": "Growth Driver", "RISK": "Risk",
    "THESIS_BREAKER": "Thesis Breaker",
    "KEY_STRENGTHS": "Key Strength", "KEY_CONCERNS": "Key Concern",
    "GROWTH_DRIVERS": "Growth Driver", "RISKS": "Risk",
    "THESIS_BREAKERS": "Thesis Breaker",
}

KNOWN_THESIS_CSS: dict[str, str] = {
    "STRENGTH": "strength", "CONCERN": "concern",
    "GROWTH_DRIVER": "driver", "RISK": "risk",
    "THESIS_BREAKER": "breaker",
    "KEY_STRENGTHS": "strength", "KEY_CONCERNS": "concern",
    "GROWTH_DRIVERS": "driver", "RISKS": "risk",
    "THESIS_BREAKERS": "breaker",
}


def build_report(ticker: str, fetcher: ReportDataFetcher | None = None) -> str:
    if fetcher is None:
        fetcher = ReportDataFetcher()
    data = fetcher.fetch(ticker)
    return _render(data)


def render_report(data: ReportData) -> str:
    return _render(data)


def _format_generated_at(val: Any) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, datetime):
        return val.strftime("%d %b %Y, %H:%M UTC")
    return str(val)


def _compute_upside(cur: float | None, fv: float | None) -> float | None:
    if cur is not None and fv is not None and cur != 0:
        return ((fv - cur) / cur) * 100
    return None


_THESIS_ORDER = [
    ("KEY_STRENGTHS", "STRENGTH"),
    ("KEY_CONCERNS", "CONCERN"),
    ("GROWTH_DRIVERS", "GROWTH_DRIVER"),
    ("RISKS", "RISK"),
    ("THESIS_BREAKERS", "THESIS_BREAKER"),
]


def _build_thesis_groups(df: pd.DataFrame) -> list[dict]:
    """Return thesis items grouped by category for bullet-point rendering."""
    if df.empty:
        return []
    # Collect items by normalized type
    bucket: dict[str, list[str]] = {}
    for _, row in df.iterrows():
        raw_type = str(row.get("item_type", "")).strip().upper()
        text = str(row.get("item_text", "")).strip()
        if not text:
            continue
        bucket.setdefault(raw_type, []).append(text)

    groups = []
    for canonical, alias in _THESIS_ORDER:
        items = bucket.get(canonical) or bucket.get(alias) or []
        if not items:
            continue
        label = KNOWN_THESIS_LABELS.get(canonical, canonical.replace("_", " ").title())
        css = KNOWN_THESIS_CSS.get(canonical, "")
        groups.append({"label": label, "css_class": css, "bullet_points": items})

    # Append any unknown types not in the ordered list
    known_keys = {k for pair in _THESIS_ORDER for k in pair}
    for raw_type, items in bucket.items():
        if raw_type not in known_keys and items:
            label = raw_type.replace("_", " ").title()
            groups.append({"label": label, "css_class": "", "bullet_points": items})

    return groups


def _build_thesis_cards(df: pd.DataFrame) -> list[dict]:
    """Legacy flat list — kept for compatibility but delegates to groups."""
    if df.empty:
        return []
    cards = []
    for _, row in df.iterrows():
        raw_type = str(row.get("item_type", "")).strip().upper()
        text = str(row.get("item_text", "")).strip()
        if not text:
            continue
        label = KNOWN_THESIS_LABELS.get(raw_type, f"Thesis ({raw_type})")
        css = KNOWN_THESIS_CSS.get(raw_type, "")
        cards.append({"label": label, "text": text, "css_class": css})
    return cards


def _build_analyst_intelligence(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Consolidated analyst findings grouped by theme/category.

    Returns a flat list of finding dicts, each with analyst attribution,
    for rendering in a single consolidated section.
    """
    if df.empty:
        return []
    findings = []
    for _, row in df.iterrows():
        conf = _safe_float(row.get("confidence"))
        findings.append({
            "analyst": str(row.get("analyst", "Unknown Analyst")),
            "category": row.get("category"),
            "title": row.get("title"),
            "statement": row.get("statement"),
            "confidence": conf,
            "confidence_label": _confidence_label(conf),
            "confidence_color": _confidence_color(conf),
            "fundamental_observation": row.get("fundamental_observation"),
            "why_it_matters": row.get("why_it_matters"),
            "positive_implication": row.get("positive_implication"),
            "negative_implication": row.get("negative_implication"),
            "thesis_breaker": row.get("thesis_breaker"),
            "evidence_ids": row.get("evidence_ids"),
        })
    return findings


def _build_scenario_cards(df: pd.DataFrame) -> list[dict[str, str]]:
    if df.empty:
        return []
    cards = []
    for _, row in df.iterrows():
        scenario = str(row.get("scenario", "")).strip().upper()
        desc = str(row.get("description", "")).strip()
        css_map = {"BULL": "bull", "BASE": "base", "BEAR": "bear"}
        css = css_map.get(scenario, "")
        cards.append({"scenario": scenario, "description": desc if desc else "No description available.", "css_class": css})
    return cards


# ------------------------------------------------------------------
# Confidence helpers
# ------------------------------------------------------------------

def _confidence_label(conf: float | None) -> str:
    if conf is None:
        return "N/A"
    if conf >= 0.8:
        return "High"
    if conf >= 0.5:
        return "Medium"
    return "Low"


def _confidence_color(conf: float | None) -> str:
    if conf is None:
        return "#94a3b8"
    if conf >= 0.8:
        return "#059669"
    if conf >= 0.5:
        return "#d97706"
    return "#dc2626"


# ------------------------------------------------------------------
# Evidence summary (grouped by domain)
# ------------------------------------------------------------------

def _canonicalize_evidence_label(label: str | None) -> str:
    """Normalize an evidence label to its canonical metric name.
    
    This helps group duplicate representations of the same metric.
    """
    if not label:
        return ""
    lbl = label.strip().upper()
    # Map known variations to canonical names
    mapping = {
        "ROE": "ROE", "RETURN ON EQUITY": "ROE", "RETURN ON EQUITY (ROE)": "ROE",
        "ROA": "ROA", "RETURN ON ASSETS": "ROA", "RETURN ON ASSETS (ROA)": "ROA",
        "NIM": "NIM", "NET INTEREST MARGIN": "NIM", "NET INTEREST MARGIN (NIM)": "NIM",
        "CASA": "CASA RATIO", "CASA RATIO": "CASA RATIO", "CASA%": "CASA RATIO",
        "COST TO INCOME": "COST TO INCOME", "COST-TO-INCOME": "COST TO INCOME", "COST TO INCOME RATIO": "COST TO INCOME",
        "GROSS NPA": "GROSS NPA", "GROSS NPA RATIO": "GROSS NPA", "GNPA": "GROSS NPA",
        "NET NPA": "NET NPA", "NET NPA RATIO": "NET NPA", "NNPA": "NET NPA",
        "EPS": "EPS", "EARNINGS PER SHARE": "EPS", "EARNINGS PER SHARE (EPS)": "EPS",
        "BVPS": "BVPS", "BOOK VALUE PER SHARE": "BVPS", "BOOK VALUE PER SHARE (BVPS)": "BVPS",
        "CREDIT COST": "CREDIT COST", "CREDIT COST (COC)": "CREDIT COST", "COC": "CREDIT COST",
        "PE": "P/E", "P/E": "P/E", "PRICE TO EARNINGS": "P/E", "PRICE-TO-EARNINGS": "P/E",
        "PB": "P/B", "P/B": "P/B", "PRICE TO BOOK": "P/B", "PRICE-TO-BOOK": "P/B",
        "JUSTIFIED P/E": "JUSTIFIED P/E", "JUSTIFIED PE": "JUSTIFIED P/E",
        "JUSTIFIED P/B": "JUSTIFIED P/B", "JUSTIFIED PB": "JUSTIFIED P/B",
        "SUSTAINABLE GROWTH RATE": "SGR", "SGR": "SGR",
        "COST OF EQUITY": "COST OF EQUITY", "COE": "COST OF EQUITY",
        "DIVIDEND PAYOUT RATIO": "DIVIDEND PAYOUT", "DIVIDEND PAYOUT": "DIVIDEND PAYOUT",
        "DIVIDEND DISCOUNT MODEL": "DDM", "DDM": "DDM",
        "RESIDUAL INCOME": "RESIDUAL INCOME", "RESIDUAL INCOME MODEL": "RESIDUAL INCOME",
        "FAIR VALUE": "FAIR VALUE", "BLENDED FAIR VALUE": "FAIR VALUE",
        "CURRENT PRICE": "CURRENT PRICE", "MARKET PRICE": "CURRENT PRICE",
        "UPSIDE": "UPSIDE", "UPSIDE/DOWNSIDE": "UPSIDE",
    }
    return mapping.get(lbl, lbl)


def _is_calculator_evidence(source: str | None, tag: str | None) -> bool:
    """Return True if the evidence row is a calculator-derived value."""
    if source and "calculator" in str(source).lower():
        return True
    if tag and "calculator" in str(tag).lower():
        return True
    return False


def _is_model_evidence(label: str | None, source: str | None, tag: str | None) -> bool:
    """Return True if the evidence row is a model/calculation/valuation output
    that should NOT appear in the main investor Evidence Trail.

    These are InvestIQ calculator outputs, valuation model intermediates,
    or raw formula expressions — not primary source evidence.
    """
    if _is_calculator_evidence(source, tag):
        return True

    lbl = (label or "").strip().upper()
    calculated_labels = {
        "JUSTIFIED P/B", "JUSTIFIED PB", "JUSTIFIED P/E", "JUSTIFIED PE",
        "SUSTAINABLE GROWTH RATE", "SGR",
        "COST OF EQUITY", "COE",
        "DIVIDEND PAYOUT RATIO", "DIVIDEND PAYOUT",
        "DIVIDEND DISCOUNT MODEL", "DDM",
        "RESIDUAL INCOME", "RESIDUAL INCOME MODEL",
        "FAIR VALUE", "BLENDED FAIR VALUE",
        "JUSTIFIED FAIR VALUE",
        "CURRENT PRICE",
        "UPSIDE", "UPSIDE/DOWNSIDE",
        "PE", "P/E", "PRICE TO EARNINGS", "PRICE-TO-EARNINGS",
        "PB", "P/B", "PRICE TO BOOK", "PRICE-TO-BOOK",
        "JUSTIFIED MULTIPLE",
    }
    if lbl in calculated_labels:
        return True

    # No longer catch formula expressions — primary-source evidence
    # can legitimately contain formulas (e.g. "ROE = Net Profit / Avg Equity = 15.42%")
    # and should not be classified as model evidence.

    return False

def _clean_evidence_label(label: str | None) -> str:
    """Extract a clean display label from formula-style evidence.

    Examples:
        "ROE = Net Profit / Avg Equity = 15.42%"   -> "ROE"
        "NIM = NII / Avg Total Assets = 3.27%"       -> "NIM"
        "CASA Ratio = CASA / Total Deposits = 34.96%" -> "CASA Ratio"
        "Cost-to-Income = Opex / Operating Income = 41.51%" -> "Cost-to-Income"
        "Return on Equity (ROE) FY2025"               -> "Return on Equity (ROE) FY2025"
        "Strong NIM"                                   -> "Strong NIM"
    """
    if not label:
        return ""
    lbl = label.strip()
    if "=" in lbl:
        # Take everything before the first "=" as the metric name
        metric = lbl.split("=", 1)[0].strip()
        return metric
    return lbl

def _build_evidence_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Group evidence by domain for compact presentation, excluding
    model/calculation/valuation outputs from the main view.

    The main view (grp.list) contains only primary-source evidence
    that supports the investment thesis.
    The detailed view (grp.all) preserves ALL evidence including
    calculator outputs, valuation intermediates, and raw formulas.
    """
    if df.empty:
        return []
    domain_groups: dict[str, list] = {}
    for _, row in df.iterrows():
        domain = str(row.get("domain", "Other")).strip() or "Other"
        label = row.get("label", "")
        value = row.get("value")
        source = row.get("source")
        tag = row.get("tag")
        canonical = _canonicalize_evidence_label(label)
        is_model = _is_model_evidence(label, source, tag)
        item = {
            "evidence_id": row.get("evidence_id", ""),
            "tag": tag, "source": source, "source_url": row.get("source_url"),
            "label": label, "clean_label": _clean_evidence_label(label),
            "value": value, "domain": domain,
            "canonical": canonical, "is_model": is_model,
        }
        domain_groups.setdefault(domain, []).append((canonical, value, is_model, item))

    result = []
    for domain, raw_items in domain_groups.items():
        all_items = []
        for (canonical, value, is_model, item) in raw_items:
            all_items.append(item)

        seen: set[str] = set()
        primary_list = []
        for (canonical, value, is_model, item) in raw_items:
            if is_model:
                continue
            if not canonical:
                primary_list.append(item)
                continue
            key = canonical + "|" + (str(value) if value is not None else "")
            if key not in seen:
                seen.add(key)
                primary_list.append(item)

        result.append({"domain": domain, "list": primary_list, "all": all_items})
    return result


def _snapshot_signature(row) -> str:
    """Generate a signature for deduplicating snapshot entries."""
    parts = [
        str(row.get("overall_assessment", "")),
        str(row.get("valuation_verdict", "")),
        str(_safe_float(row.get("current_price"))),
        str(_safe_float(row.get("blended_fair_value"))),
        str(row.get("executive_summary", "")),
        str(row.get("investment_thesis", "")),
    ]
    return "|".join(parts)


def _build_history_timeline(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Build a chronological research timeline with at most two
    meaningfully distinct snapshots.

    Returns entries sorted newest first, each with snapshot data.
    Duplicate consecutive snapshots (identical research content)
    are suppressed.  Only the current and previous distinct snapshots
    are returned, and changes between them are computed.
    """
    if df.empty:
        return []
    entries = []
    for _, row in df.iterrows():
        sid = str(row.get("snapshot_id", ""))
        entries.append({
            "snapshot_id": sid,
            "snapshot_id_short": sid[:8] + "..." if len(sid) > 11 else sid,
            "generated_at": _format_generated_at(row.get("generated_at")),
            "current_price": _safe_float(row.get("current_price")),
            "blended_fair_value": _safe_float(row.get("blended_fair_value")),
            "valuation_verdict": row.get("valuation_verdict"),
            "overall_assessment": row.get("overall_assessment"),
            "executive_summary": row.get("executive_summary"),
            "investment_thesis": row.get("investment_thesis"),
            "_sig": _snapshot_signature(row),
        })
    # entries are already sorted DESC from the query
    # Deduplicate: keep the first occurrence of each distinct signature
    seen_sigs: set[str] = set()
    distinct = []
    for entry in entries:
        sig = entry["_sig"]
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            distinct.append(entry)

    # Keep at most two distinct entries (current + previous)
    distinct = distinct[:2]

    # Compute changes between current and previous
    if len(distinct) >= 2:
        cur = distinct[0]
        prev = distinct[1]
        changes = []
        for field, label, fmt in [
            ("blended_fair_value", "Fair value", "₹{:,.2f}"),
            ("current_price", "Price", "₹{:,.2f}"),
            ("valuation_verdict", "Valuation", "{}"),
            ("overall_assessment", "Overall assessment", "{}"),
        ]:
            c_val = cur.get(field)
            p_val = prev.get(field)
            if c_val is not None and p_val is not None and c_val != p_val:
                changes.append({
                    "label": label,
                    "from_val": p_val,
                    "to_val": c_val,
                    "direction": "up" if (isinstance(c_val, (int, float)) and isinstance(p_val, (int, float)) and c_val > p_val) else "down",
                })
            elif str(c_val) != str(p_val) if c_val is not None or p_val is not None else False:
                changes.append({
                    "label": label,
                    "from_val": p_val,
                    "to_val": c_val,
                    "direction": "changed",
                })

        if changes:
            distinct[0]["changes"] = changes
        else:
            distinct[0]["no_changes"] = True

    # Remove internal signature from output
    for entry in distinct:
        entry.pop("_sig", None)

    return distinct


# ------------------------------------------------------------------
# Render
# ------------------------------------------------------------------

def _render(data: ReportData) -> str:
    upside = _compute_upside(data.current_price, data.blended_fair_value)

    # Build history timeline and compute changes for the latest entry
    history_entries = _build_history_timeline(data.history)
    is_first_snapshot = not history_entries

    template = _env.get_template("research_report.html")
    html = template.render(
        company_name=data.company_name or data.ticker,
        ticker=data.ticker, sector=data.sector,
        company_type=data.company_type,
        generated_at=_format_generated_at(data.generated_at),
        snapshot_id=data.snapshot_id,
        overall_assessment=data.overall_assessment,
        current_price=data.current_price,
        blended_fair_value=data.blended_fair_value,
        upside_pct=upside,
        valuation_verdict=data.valuation_verdict,
        num_findings=data.num_findings,
        num_metrics_years=data.num_metrics_years,
        executive_summary=data.executive_summary,
        investment_thesis=data.investment_thesis,
        thesis_groups=_build_thesis_groups(data.thesis_items),
        metric_charts=render_all_metric_charts(data.metrics),
        analyst_findings=_build_analyst_intelligence(data.findings),
        scenario_cards=_build_scenario_cards(data.scenarios),
        evidence_groups=_build_evidence_summary(data.evidence),
        history_entries=history_entries,
        is_first_snapshot=is_first_snapshot,
    )
    return html



def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------------
# Backward-compatible aliases
# ------------------------------------------------------------------
_build_analyst_groups = _build_analyst_intelligence
_build_evidence_rows = _build_evidence_summary
_build_history_rows = _build_history_timeline