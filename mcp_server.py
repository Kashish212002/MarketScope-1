import os
import json
import sys
from contextlib import redirect_stdout
from typing import Any

from mcp.server.fastmcp import FastMCP
from source_research import search_market
from market_calculator import (
    calculate_bottom_up as _calculate_bottom_up,
    calculate_cagr as _calculate_cagr,
    calculate_gpu_market as _calculate_gpu_market,
    forecast_market as _forecast_market,
)
from marketscope_assessment_upgrade import (
    validate_evidence_pack,
    build_assessment_instructions,
    calculate_tam_sam,
)

mmcp = FastMCP(
    "MarketScope",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "10000"))
)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _run_quietly(function, *args, **kwargs):
    """Keep module print statements out of the MCP protocol stream."""
    with redirect_stdout(sys.stderr):
        return function(*args, **kwargs)


@mcp.tool()
def check_marketscope_status() -> str:
    """Check whether MarketScope is online and list its available tools."""
    return _json({
        "status": "online",
        "application": "MarketScope",
        "architecture": "API-key-independent research, evidence-triage and calculation layer",
        "available_tools": [
            "check_marketscope_status",
            "search_market_evidence",
            "run_market_assessment",
            "calculate_bottom_up_market",
            "calculate_cagr",
            "forecast_market",
            "calculate_tam_sam_market",
            "calculate_gpu_market",
        ],
    })


@mcp.tool()
def search_market_evidence(industry: str, geography: str) -> str:
    """Search a market and prioritise evidence leads using relevance and transparency signals."""
    sources = _run_quietly(search_market, industry, geography)
    validation = validate_evidence_pack(sources, industry, geography)
    return _json({
        "industry": industry,
        "geography": geography,
        "source_count": len(sources) if isinstance(sources, list) else None,
        "evidence_validation": {
            key: value for key, value in validation.items() if key != "sources"
        },
        "sources": validation["sources"],
        "note": (
            "Research priority is a triage score, not a source-quality verdict. "
            "Open original sources and inspect methodology before relying on claims."
        ),
    })


@mcp.tool()
def run_market_assessment(
    industry: str,
    geography: str,
    objective: str = "Complete market assessment",
) -> str:
    """
    Run a complete consulting-style market assessment.
    The user only needs to provide industry and geography. The full report structure,
    research methodology, evidence rules, market sizing and output standards are embedded.
    """
    sources = _run_quietly(search_market, industry, geography)
    validation = validate_evidence_pack(sources, industry, geography)
    instructions = build_assessment_instructions(industry, geography)

    return _json({
        "status": "evidence_ready",
        "industry": industry,
        "geography": geography,
        "objective": objective,
        "source_count": len(sources) if isinstance(sources, list) else None,
        "evidence_validation": {
            key: value for key, value in validation.items() if key != "sources"
        },
        "sources": validation["sources"],
        "assessment_structure": [
            "Executive summary",
            "1. Market overview and definition",
            "2. Market trends",
            "3. Demand drivers",
            "4. Growth factors and outlook",
            "5. Demand analysis and bottom-up sizing",
            "6. Supply analysis and top-down sizing",
            "7. TAM and SAM",
            "8. Market reconciliation",
            "9. Competitive landscape",
            "10. Risks and opportunities",
            "11. Key news and market impact",
            "12. Outlook and implications",
            "13. Evidence register and data gaps",
        ],
        "instructions_for_analysis": instructions,
        "important_evidence_limitation": validation["important_limitation"],
        "interviewer_usage": (
            "The interviewer can simply ask: 'Assess [industry] in [geography].' "
            "The detailed methodology and report prompt are embedded in this tool."
        ),
        "note": (
            "MarketScope retrieves evidence and performs automated metadata triage. "
            "Claude Desktop performs the narrative synthesis. This server does not "
            "call the Anthropic API."
        ),
    })


@mcp.tool()
def calculate_bottom_up_market(volume: float, price_per_unit: float) -> str:
    """Calculate bottom-up market value using volume and price per unit."""
    result = _run_quietly(_calculate_bottom_up, volume, price_per_unit)
    return _json({
        "method": "bottom_up",
        "volume": volume,
        "price_per_unit": price_per_unit,
        "result": result,
    })


@mcp.tool()
def calculate_cagr(start_value: float, end_value: float, years: float) -> str:
    """Calculate CAGR from start value, end value and number of years."""
    result = _run_quietly(_calculate_cagr, start_value, end_value, years)
    return _json({
        "method": "CAGR",
        "start_value": start_value,
        "end_value": end_value,
        "years": years,
        "result": result,
    })


@mcp.tool()
def forecast_market(current_value: float, annual_growth_rate: float, years: float) -> str:
    """Forecast market value using annual growth rate and forecast horizon."""
    result = _run_quietly(
        _forecast_market, current_value, annual_growth_rate, years
    )
    return _json({
        "method": "market_forecast",
        "current_value": current_value,
        "annual_growth_rate": annual_growth_rate,
        "years": years,
        "result": result,
    })


@mcp.tool()
def calculate_tam_sam_market(
    tam_value: float | None = None,
    sam_share_of_tam_pct: float | None = None,
    bottom_up_units: float | None = None,
    annual_frequency: float | None = None,
    average_price: float | None = None,
    serviceable_share_pct: float | None = None,
    currency: str = "INR",
    period: str = "annual",
) -> str:
    """Calculate TAM and SAM from a top-down TAM or bottom-up operating inputs."""
    result = calculate_tam_sam(
        tam_value=tam_value,
        sam_share_of_tam_pct=sam_share_of_tam_pct,
        bottom_up_units=bottom_up_units,
        annual_frequency=annual_frequency,
        average_price=average_price,
        serviceable_share_pct=serviceable_share_pct,
        currency=currency,
        period=period,
    )
    return _json({
        "method": "TAM_SAM",
        "inputs": {
            "tam_value": tam_value,
            "sam_share_of_tam_pct": sam_share_of_tam_pct,
            "bottom_up_units": bottom_up_units,
            "annual_frequency": annual_frequency,
            "average_price": average_price,
            "serviceable_share_pct": serviceable_share_pct,
            "currency": currency,
            "period": period,
        },
        "result": result,
    })


@mcp.tool()
def calculate_gpu_market(
    gpu_count: float,
    hours_per_day: float,
    utilisation: float,
    price_per_hour: float,
    operating_days: int = 365,
) -> str:
    """Estimate GPU-market revenue from GPU count, hours, utilisation and hourly price."""
    result = _run_quietly(
        _calculate_gpu_market,
        gpu_count,
        hours_per_day,
        utilisation,
        price_per_hour,
        operating_days,
    )
    return _json({
        "method": "GPU_market_revenue",
        "gpu_count": gpu_count,
        "hours_per_day": hours_per_day,
        "utilisation": utilisation,
        "price_per_hour": price_per_hour,
        "operating_days": operating_days,
        "result": result,
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http")