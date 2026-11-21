"""
MarketScope assessment upgrade helpers.

This module performs metadata/evidence triage and transparent market-sizing
calculations. It does NOT independently verify the truth of a source's claims.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from urllib.parse import urlparse
import re
from typing import Any


def _normalise_url(url: str) -> str:
    try:
        parsed = urlparse((url or "").strip())
        host = (parsed.netloc or "").lower().removeprefix("www.")
        path = (parsed.path or "").rstrip("/")
        return f"{host}{path}".lower()
    except Exception:
        return (url or "").strip().lower()




def _classify_source(item: dict[str, Any]) -> tuple[str, str]:
    """Provisional source-type classification from visible metadata only."""
    title = str(item.get("title") or "").lower()
    content = str(item.get("content") or "").lower()
    domain = str(item.get("domain") or "").lower()
    url = str(item.get("url") or "").lower()
    host = domain or url

    primary_domains = (".gov", "gov.in", "rbi.org.in", "sebi.gov.in",
                       "mospi.gov.in", "data.gov.in")
    primary_terms = ("annual report", "investor presentation", "exchange filing",
                     "regulatory filing", "official statistics", "government notification",
                     "official press release", "company press release",
                     "company announcement", "results announcement")
    tertiary_terms = ("personal blog", "guest post", "sponsored post",
                      "forum discussion", "reddit.com", "quora.com",
                      "medium.com", "substack.com")
    secondary_terms = ("market research", "industry report", "market report",
                        "research report", "industry analysis", "news")

    if any(term in host for term in primary_domains):
        return "Primary", "Government or regulatory domain; confirm the specific document and data provenance"
    if any(term in title or term in content for term in primary_terms):
        return "Primary", "Appears to be an original company, filing or official disclosure; open and confirm"
    if any(term in host for term in tertiary_terms):
        return "Tertiary", "Blog, social or user-generated source; seek independent corroboration"
    if any(term in title or term in content for term in secondary_terms):
        return "Secondary", "Commercial research, industry analysis or media; inspect methodology and upstream citations"
    if any(term in host for term in ("grandviewresearch", "credenceresearch",
                                     "imarcgroup", "marketsandmarkets",
                                     "fortunebusinessinsights", "mordorintelligence")):
        return "Secondary", "Commercial market-research publisher; methodology and scope require inspection"
    return "Unknown", "Source type cannot be established from available metadata"



def _classify_source(item: dict[str, Any]) -> tuple[str, str]:
    # Provisional classification from visible metadata only.
    title = str(item.get("title") or "").lower()
    content = str(item.get("content") or "").lower()
    domain = str(item.get("domain") or "").lower()
    url = str(item.get("url") or "").lower()
    host = domain or url
    primary_domains = (".gov", "gov.in", "rbi.org.in", "sebi.gov.in", "mospi.gov.in", "data.gov.in")
    primary_terms = ("annual report", "investor presentation", "exchange filing", "regulatory filing",
                     "official statistics", "government notification", "official press release",
                     "company press release", "company announcement", "results announcement")
    tertiary_domains = ("reddit.com", "quora.com", "medium.com", "substack.com")
    secondary_domains = ("grandviewresearch", "credenceresearch", "imarcgroup", "marketsandmarkets",
                         "fortunebusinessinsights", "mordorintelligence")
    if any(term in host for term in primary_domains):
        return "Primary", "Government or regulatory domain; confirm the document and data provenance"
    if any(term in title or term in content for term in primary_terms):
        return "Primary", "Possible original company or official disclosure; open and confirm"
    if any(term in host for term in tertiary_domains):
        return "Tertiary", "Blog, social or user-generated source; seek corroboration"
    if any(term in host for term in secondary_domains):
        return "Secondary", "Commercial market-research publisher; inspect methodology and scope"
    if any(term in title or term in content for term in ("market research", "industry report", "market report", "industry analysis", "news")):
        return "Secondary", "Likely research, industry analysis or media; inspect upstream citations"
    return "Unknown", "Source type cannot be established from available metadata"


def _source_priority(item: dict[str, Any], industry: str, geography: str) -> tuple[int, list[str]]:
    # Discovery triage only; not a source-quality, verification or truth score.
    text = f"{item.get('title') or ''} {item.get('content') or ''}".lower()
    score, reasons = 0, []
    source_class, _ = _classify_source(item)
    if source_class == "Primary":
        score += 3
        reasons.append("Provisional primary-source lead; original document still needs checking")
    elif source_class == "Secondary":
        score += 1
        reasons.append("Secondary source; use as cross-check, not automatic ground truth")
    elif source_class == "Tertiary":
        score -= 1
        reasons.append("Tertiary source; seek original underlying source")
    industry_terms = re.findall(r"[a-zA-Z]{4,}", industry or "")
    geography_terms = re.findall(r"[a-zA-Z]{3,}", geography or "")
    if industry_terms and any(term.lower() in text for term in industry_terms):
        score += 2
        reasons.append("Snippet appears relevant to requested industry")
    if geography_terms and any(term.lower() in text for term in geography_terms):
        score += 2
        reasons.append("Snippet appears relevant to requested geography")
    method_terms = ("methodology", "sample size", "survey", "primary research", "data sources",
                    "scope", "definition", "revenue", "market size")
    matched = [term for term in method_terms if term in text]
    if len(matched) >= 3:
        score += 2
        reasons.append("Several methodology/definition signals appear in snippet; inspect full source")
    elif matched:
        score += 1
        reasons.append("Some methodology/definition signals appear in snippet; inspect full source")
    if re.search(r"\d+(?:\.\d+)?\s*(?:%|billion|million|bn|mn|cr|crore|mw|gw)", text):
        score += 1
        reasons.append("Contains a quantitative claim worth tracing")
    if str(item.get("source_tier") or "").lower() == "tier 1":
        score += 1
        reasons.append("Publisher tier used only as a weak tie-breaker")
    return score, reasons


def validate_evidence_pack(
    sources: list[dict[str, Any]],
    industry: str = "",
    geography: str = "",
) -> dict[str, Any]:
    # Metadata checks and provisional source classification; no claim verification.
    seen_urls: set[str] = set()
    rows = []
    tier_counts, class_counts, issue_counts = Counter(), Counter(), Counter()
    for index, source in enumerate(sources or [], start=1):
        item = dict(source or {})
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or "").strip()
        domain = str(item.get("domain") or "").strip().lower()
        tier = str(item.get("source_tier") or "Unclassified").strip()
        issues = []
        parsed = urlparse(url)
        if not title:
            issues.append("Missing title")
        if not content:
            issues.append("Missing supporting content or snippet")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            issues.append("Missing or invalid source URL")
        if not domain and parsed.netloc:
            domain = parsed.netloc.lower().removeprefix("www.")
        if domain and parsed.netloc and domain not in parsed.netloc.lower():
            issues.append("Domain metadata does not match URL")
        normal_url = _normalise_url(url)
        duplicate = bool(normal_url and normal_url in seen_urls)
        if duplicate:
            issues.append("Possible duplicate URL")
        elif normal_url:
            seen_urls.add(normal_url)
        enriched = {**item, "domain": domain}
        source_class, class_reason = _classify_source(enriched)
        priority_score, priority_reasons = _source_priority(enriched, industry, geography)
        tier_counts[tier] += 1
        class_counts[source_class] += 1
        for issue in issues:
            issue_counts[issue] += 1
        item.update({
            "evidence_id": f"E{index:03d}",
            "domain": domain or None,
            "source_classification": source_class,
            "source_classification_basis": class_reason,
            "metadata_validation": "review_required" if issues else "basic_checks_passed",
            "verification_status": "not_independently_verified",
            "confidence": "unassessed",
            "research_priority_score": priority_score,
            "research_priority": ("higher review priority" if priority_score >= 7
                                  else "medium review priority" if priority_score >= 4
                                  else "lower review priority"),
            "priority_reasons": priority_reasons,
            "possible_duplicate": duplicate,
            "validation_issues": issues,
            "verification_needed": True,
        })
        rows.append(item)
    rows.sort(key=lambda row: row.get("research_priority_score", 0), reverse=True)
    total = len(rows)
    return {
        "industry": industry,
        "geography": geography,
        "total_sources": total,
        "independently_verified_sources": 0,
        "not_independently_verified_sources": total,
        "source_tier_distribution": dict(tier_counts),
        "source_classification_distribution": dict(class_counts),
        "validation_issue_counts": dict(issue_counts),
        "important_limitation": (
            "Source classifications and priority scores are provisional metadata-based triage only. "
            "No source has been opened or independently verified by this function. They do not establish "
            "authenticity, accuracy, independence, recency or methodology quality. Open original documents, "
            "inspect methods and trace material claims upstream."
        ),
        "sources": rows,
    }


def _positive_number(value: Any, field: str) -> float:
    number = float(value)
    if number < 0:
        raise ValueError(f"{field} cannot be negative")
    return number


def calculate_tam_sam(
    *,
    tam_value: float | None = None,
    sam_share_of_tam_pct: float | None = None,
    bottom_up_units: float | None = None,
    annual_frequency: float | None = None,
    average_price: float | None = None,
    serviceable_share_pct: float | None = None,
    currency: str = "INR",
    period: str = "annual",
) -> dict[str, Any]:
    """
    Transparent TAM/SAM calculator.

    TAM can be supplied directly or calculated as units x annual frequency x price.
    SAM requires an explicit serviceable-market share. Inputs and assumptions
    must be sourced or explicitly labelled by the assessment author.
    """
    assumptions = []
    if tam_value is None:
        required = (bottom_up_units, annual_frequency, average_price)
        if any(value is None for value in required):
            raise ValueError(
                "Provide tam_value, or provide bottom_up_units, annual_frequency "
                "and average_price to calculate TAM."
            )
        units = _positive_number(bottom_up_units, "bottom_up_units")
        frequency = _positive_number(annual_frequency, "annual_frequency")
        price = _positive_number(average_price, "average_price")
        tam = units * frequency * price
        assumptions.append(
            "TAM calculated as addressable units Ã— annual purchase/service frequency Ã— average price."
        )
        tam_method = "bottom_up"
    else:
        tam = _positive_number(tam_value, "tam_value")
        tam_method = "provided_top_down_or_external_estimate"

    sam_pct = sam_share_of_tam_pct
    if sam_pct is None:
        sam_pct = serviceable_share_pct

    sam = None
    if sam_pct is not None:
        sam_pct = float(sam_pct)
        if not 0 <= sam_pct <= 100:
            raise ValueError("SAM share must be between 0 and 100")
        sam = tam * sam_pct / 100
        assumptions.append(
            "SAM calculated by applying the stated serviceable-market share to TAM."
        )

    return {
        "currency": currency,
        "period": period,
        "tam": round(tam, 2),
        "tam_method": tam_method,
        "sam": round(sam, 2) if sam is not None else None,
        "sam_share_of_tam_pct": sam_pct,
        "assumptions": assumptions,
        "limitations": [
            "SAM requires an explicit and defensible serviceability filter.",
            "Inputs and shares must be supported by cited evidence or explicitly labelled assumptions.",
            "A calculated result is not independently validated market fact.",
        ],
        "status": "complete" if sam is not None else "tam_only",
    }


ASSESSMENT_STRUCTURE = [
    ("Executive summary", "Lead with 3â€“5 decision-relevant findings, market size range, growth outlook and confidence."),
    ("1. Market overview and definition", "Introduce the market, define products/services, customers, geography, value chain, units and exclusions; establish current market size and context."),
    ("2. Market trends", "Present the major market trends shaping the industry, including technology, customer behaviour, business models, pricing, regulation and investment where relevant."),
    ("3. Demand drivers", "Explain the structural factors driving customer adoption, usage and spending; quantify each driver where evidence permits."),
    ("4. Growth factors and outlook", "Separate secular growth factors from short-term catalysts; state direction, magnitude where supportable and time horizon."),
    ("5. Demand analysis and bottom-up sizing", "Size customers/units Ã— adoption or penetration Ã— frequency Ã— average price. Show low/base/high cases and label assumptions."),
    ("6. Supply analysis and top-down sizing", "Assess active capacity, utilization, suppliers, planned capacity, channels and constraints; reconcile published market estimates."),
    ("7. TAM and SAM", "Calculate TAM and SAM where inputs permit. Show formulas, scope filters, sources, assumptions, period and confidence. Never silently omit either metric; explain exactly why a metric cannot be estimated."),
    ("8. Market reconciliation", "Compare bottom-up demand and top-down supply/market estimates; explain gaps, definitions, years, currency and scope differences."),
    ("9. Competitive landscape", "Compare players by segment, geography, scale, pricing, capacity, positioning and evidence quality. Do not invent market shares."),
    ("10. Risks and opportunities", "Rank by likelihood, impact, time horizon and evidence; connect each to market economics."),
    ("11. Key news and market impact", "For each item show event date, announcement date, company, development, market impact, direction, horizon, original source and verification status."),
    ("12. Outlook and implications", "Present scenarios, leading indicators, strategic implications and what would change the conclusion."),
    ("13. Evidence register and data gaps", "List source, publisher tier, metric, geography, period, methodology, verification status, confidence and unresolved gaps."),
]




def build_assessment_instructions(industry: str, geography: str) -> str:
    sections = "\\n".join(f"{name}: {detail}" for name, detail in ASSESSMENT_STRUCTURE)
    return f"""
You are preparing a rigorous, consulting-style market assessment for {industry} in {geography}.

Use this exact report sequence:
{sections}

SOURCE CLASSIFICATION AND EVIDENCE REVIEW
Before market estimates, create a source-priority table with evidence ID, publisher, source type, primary/secondary/tertiary/unknown classification, geography and metric relevance, period, methodology transparency, independence/upstream-source status, verification status and reason for priority.

Classify sources as follows:
- Primary: original government/statistical datasets, regulator publications, company filings, annual reports, investor presentations, official company announcements and original surveys or datasets.
- Secondary: commercial market-research reports, industry analysis, analyst commentary and media reporting.
- Tertiary: blogs, aggregators, syndicated summaries, reposts and social/user-generated content.
- Unknown: source type cannot be established from available evidence.

These are source-type labels, not credibility verdicts. A company announcement is primary for what the company announced, but not necessarily independent proof of a market-wide claim. A government source is not automatically relevant to the specific metric. Commercial publishers such as Grand View Research, Credence Research and IMARC are secondary unless original underlying data is separately identified.

Do not infer methodology quality from words in a search snippet. If the original source has not been opened, mark methodology, independence and claim verification as unknown/not checked. A URL, title, snippet or publisher name does not mean a claim is verified. Trace repeated estimates to upstream sources and flag syndicated or copied figures.

Rank evidence by direct relevance, primary/secondary status, metric-definition fit, transparent methodology, recency and independence. Publisher brand and source tier are weak tie-breakers only. Automated priority scores are research leads, not evidence-strength or truth scores. Present conflicting estimates separately when their scopes differ.

NON-NEGOTIABLE EVIDENCE RULES
- Cite every material number next to the claim and include a source register.
- Distinguish Published fact, Calculated, Assumption, Estimate and Unverified claim.
- State whether the original source was opened and checked. Separate discovery, metadata checks and actual claim verification.
- Compare definitions, geography, period, currency, units and methodology before comparing market estimates.
- Use original company disclosures, government/statistical sources, regulatory filings, industry-body datasets and transparent primary research when directly relevant. Use commercial market-research reports as cross-checks, not automatic ground truth.
- Flag conflicting estimates; do not average incompatible scopes.
- Distinguish demand-side bottom-up sizing from supply-side/top-down sizing and reconcile them.
- TAM: estimate the full theoretical market using a defensible top-down or bottom-up method.
- SAM: apply explicit serviceability filters such as geography, customer segment, product/service scope and channel.
- Always show TAM and SAM. If either cannot be estimated, state the exact missing input and why; calculate any defensible range instead of silently omitting it.
- Do not invent penetration, frequency, pricing, market share, capacity or growth assumptions. Label proxies and show low/base/high cases.
- Never fabricate market shares. If unavailable, compare players on disclosed scale and operating footprint.
- For news, verify against original announcements where possible. Separate event date from publication date.
- Explain the business implication of every major driver, risk, opportunity and news item.
- Use insight-led headings, concise paragraphs, comparison tables and calculation tables.
- Check arithmetic, units, currency conversions and CAGR independently. Ensure the executive summary range reconciles with low/base/high scenarios and distinguish observed market estimates from theoretical TAM.
- End with confidence level, key evidence gaps and the 3 most valuable next research actions.
""".strip()


def interviewer_quick_prompt(industry: str, geography: str) -> str:
    """The detailed assessment method is embedded in the MCP tool; user prompt stays short."""
    return f"Assess the {industry} market in {geography}."

