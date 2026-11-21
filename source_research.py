"""
MarketScope source research and source-quality classification.

Tier 1: official / primary evidence (including company-hosted documents for
that company's own reported information).
Tier 2: established research providers, industry bodies and reputable media.
Tier 3: blogs, forums and low-confidence commentary.
Unverified: publisher/evidence type cannot be established automatically.

Important: a tier describes the source/publisher and evidence type. It does
not prove that every claim is correct or that company-reported data is an
independent estimate of the whole market.
"""

import os
import re
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient


# ---------------------------------------------------------------------------
# API setup
# ---------------------------------------------------------------------------

load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    raise RuntimeError(
        "TAVILY_API_KEY was not found. Add it to backend/.env and restart the terminal."
    )

tavily = TavilyClient(api_key=TAVILY_API_KEY)


# ---------------------------------------------------------------------------
# Publisher classification lists
# Domain matching includes subdomains (e.g. media.company.com).
# Company domains are not listed individually; company-hosted documents
# are identified through domain + document-title/URL signals.
# ---------------------------------------------------------------------------

TIER_1_DOMAINS = [
    # Governments and regulators
    "gov.in", "gov", "nic.in", "gov.uk", "gov.au", "gc.ca", "gov.sg",
    "gov.jp", "europa.eu", "int",
    "rbi.org.in", "sebi.gov.in", "mca.gov.in", "mospi.gov.in",
    "morth.nic.in", "pib.gov.in", "niti.gov.in", "meity.gov.in",
    "mnre.gov.in", "cea.nic.in", "cpcb.nic.in", "dpiit.gov.in",
    "nabard.org", "sidbi.in",

    # Exchanges and depositories
    "nseindia.com", "bseindia.com", "msei.in", "nsdl.co.in",
    "cdslindia.com", "amfiindia.com", "nseindia.com", "nyse.com",
    "nasdaq.com", "lseg.com", "hkex.com.hk", "jpx.co.jp",

    # Multilateral organisations
    "worldbank.org", "imf.org", "bis.org", "oecd.org", "wto.org",
    "adb.org", "aiib.org", "afdb.org", "ebrd.com", "iadb.org",
    "ifc.org", "fsb.org", "iosco.org", "fatf-gafi.org", "un.org",
    "un.org", "undp.org", "ilo.org", "who.int", "unctad.org",
    "undp.org", "fao.org", "unesco.org", "wipo.int", "iea.org",
    "irena.org", "opec.org",

    # Academic and research
    "edu", "ac.in", "ac.uk", "edu.au", "arxiv.org", "nber.org",
    "ssrn.com", "nature.com", "science.org", "jstor.org",

    # Indian research institutions
    "ibef.org", "icai.org", "ncaer.org", "icrier.org", "nipfp.org.in",
]

TIER_2_DOMAINS = [
    # Market research and analyst firms
    "gartner.com", "idc.com", "omdia.com", "cbinsights.com",
    "pitchbook.com", "crunchbase.com", "tracxn.com", "inc42.com",
    "kenresearch.com", "crisil.com", "icra.in", "careedge.com",
    "indiaratings.co.in", "brickworkratings.com", "acuite.in",
    "moodys.com", "spglobal.com", "fitchratings.com",
    "morningstar.com", "msci.com", "refinitiv.com", "factset.com",
    "marketsandmarkets.com", "grandviewresearch.com",
    "fortunebusinessinsights.com", "mordorintelligence.com",
    "precedenceresearch.com", "technavio.com", "imarcgroup.com",
    "alliedmarketresearch.com", "credenceresearch.com", "statista.com",

    # Consulting and advisory
    "mckinsey.com", "bcg.com", "bain.com", "deloitte.com", "pwc.com",
    "kpmg.com", "accenture.com", "oliverwyman.com", "kearney.com",
    "rolandberger.com", "arthurdlittle.com", "nasscom.in", "ey.com",

    # Industry bodies and think tanks
    "ficci.in", "cii.in", "assocham.org", "pdafci.com",
    "brookings.edu", "carnegieendowment.org", "weforum.org",
    "piie.com", "cfr.org", "chathamhouse.org", "orfonline.org",
    "gatewayhouse.in", "cprindia.org", "idfcinstitute.org",
    "siam.in", "acma.in", "nasscom.in",

    # Business press and wire services
    "reuters.com", "ft.com", "wsj.com", "economist.com", "apnews.com",
    "bbc.com", "forbes.com", "fortune.com", "hbr.org",
    "economictimes.indiatimes.com", "livemint.com",
    "business-standard.com", "thehindubusinessline.com",
    "financialexpress.com", "moneycontrol.com", "cnbctv18.com",
    "thehindu.com", "indianexpress.com", "scmp.com", "nikkei.com",
    "caixinglobal.com", "bloomberg.com", "cnbc.com",
]

TIER_3_DOMAINS = [
    "medium.com", "substack.com", "wordpress.com", "blogspot.com",
    "reddit.com", "quora.com", "facebook.com", "linkedin.com",
]


def _normalise_domain(url):
    """Extract hostname and remove www; retain other subdomains."""
    try:
        parsed = urlparse(url if "://" in url else "//" + url)
        return (parsed.hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def _domain_matches(domain, domain_list):
    """Match exact domains and their subdomains safely."""
    for item in domain_list:
        item = item.lower().strip()
        if domain == item or domain.endswith("." + item):
            return True
    return False


def _company_label_from_domain(domain):
    """
    Infer a likely company label from a hostname, ignoring common delivery
    subdomains. Example: media.atherenergy.com -> atherenergy.
    """
    ignored = {
        "www", "media", "cdn", "static", "files", "file", "docs",
        "documents", "reports", "investor", "investors", "ir",
        "download", "downloads", "assets", "content", "blog",
        "news", "press", "corporate", "portal", "shop", "store",
    }
    parts = domain.split(".")
    for part in parts:
        if part and part not in ignored and part not in {
            "com", "org", "net", "co", "in", "gov", "edu"
        }:
            return re.sub(r"[^a-z0-9]", "", part)
    return ""


def classify_source(url):
    """
    Return a tier label for a URL string.

    This function intentionally returns a string for compatibility with code
    that calls classify_source(url).
    """
    domain = _normalise_domain(str(url or ""))
    parsed = urlparse(str(url or "") if "://" in str(url or "") else "//" + str(url or ""))
    path = (parsed.path or "").lower()
    full_url = str(url or "").lower()

    if not domain:
        return "Unverified"

    # First-party official government, regulator and institution sources.
    if _domain_matches(domain, TIER_1_DOMAINS):
        return "Tier 1"

    # Established third-party research, industry and media publishers.
    if _domain_matches(domain, TIER_2_DOMAINS):
        return "Tier 2"

    # User-generated/blog platforms should not be promoted by document signals.
    if _domain_matches(domain, TIER_3_DOMAINS):
        return "Tier 3"

    # Dynamic company-hosted document recognition:
    # the likely company label in the host must also appear in the document
    # path/title, and the URL must look like a formal document.
    company_label = _company_label_from_domain(domain)
    clean_path = re.sub(r"[^a-z0-9]", "", path)
    document_signal = (
        path.endswith(".pdf")
        or any(term in full_url for term in (
            "annual-report", "annual_report", "investor-presentation",
            "investor_presentation", "financial-results", "industry-report",
            "industry_report", "quarterly-results", "quarterly_results",
            "earnings-release", "earnings_release",
        ))
    )

    if (
        len(company_label) >= 5
        and company_label in clean_path
        and document_signal
    ):
        return "Tier 1"

    return "Unverified"


def classify_source_details(url, title="", content=""):
    """Return tier plus a transparent explanation for display/audit."""
    tier = classify_source(url)
    domain = _normalise_domain(url)

    if tier == "Tier 1":
        if _domain_matches(domain, TIER_1_DOMAINS):
            return {
                "source_tier": tier,
                "source_type": "Official / institutional / primary source",
                "classification_reason": "Publisher matches an official government, regulator, academic or institutional domain.",
                "evidence_scope": "Use for official statistics, regulation, policy or institutional research.",
                "independence": "Institutional / primary",
            }
        return {
            "source_tier": tier,
            "source_type": "Likely company-hosted primary document",
            "classification_reason": "Company identity in the hostname matches a formal document hosted on that domain.",
            "evidence_scope": "Primary evidence for the company's own reported information; not automatically an independent market estimate.",
            "independence": "First-party; not independent",
        }

    if tier == "Tier 2":
        return {
            "source_tier": tier,
            "source_type": "Established research / industry / media publisher",
            "classification_reason": "Publisher matches a recognised research provider, industry body, advisory firm or media domain.",
            "evidence_scope": "Use for triangulation; inspect methodology and trace material figures to underlying sources.",
            "independence": "Generally third-party",
        }

    if tier == "Tier 3":
        return {
            "source_tier": tier,
            "source_type": "Blog / social / user-generated platform",
            "classification_reason": "Publisher is a blog, social or user-generated-content platform.",
            "evidence_scope": "Context and research leads only; do not rely on it alone for market-size figures.",
            "independence": "Variable / unverified",
        }

    return {
        "source_tier": "Unverified",
        "source_type": "Publisher not confidently classified",
        "classification_reason": "No reliable publisher category or first-party document signal was identified automatically.",
        "evidence_scope": "Treat as a lead until publisher identity and underlying evidence are checked.",
        "independence": "Unknown",
    }


# ---------------------------------------------------------------------------
# Search and result normalisation
# ---------------------------------------------------------------------------

def _normalise_result(result, research_query):
    url = result.get("url", "")
    title = result.get("title", "Untitled source")
    content = result.get("content", "")

    source = {
        "title": title,
        "url": url,
        "content": content,
        "score": result.get("score", 0),
        "research_query": research_query,
        "domain": _normalise_domain(url),
    }
    source.update(classify_source_details(url, title, content))
    return source


def _run_search_queries(queries, max_results=4):
    collected = {}

    for query in queries:
        try:
            print(f"Searching: {query}")
            response = tavily.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=False,
            )

            for result in response.get("results", []):
                source = _normalise_result(result, query)
                url = source.get("url")
                if not url:
                    continue

                old = collected.get(url)
                if old is None or source.get("score", 0) > old.get("score", 0):
                    collected[url] = source

        except Exception as exc:
            print(f"Search warning for '{query}': {exc}")

    return sorted(
        collected.values(),
        key=lambda item: item.get("score", 0),
        reverse=True,
    )


def build_research_queries(industry, geography):
    """Industry-agnostic searches covering market size and sizing variables."""
    return [
        f"{industry} {geography} market definition market size revenue",
        f"{industry} {geography} industry revenue historical market value",
        f"{industry} {geography} customers users units sales volume adoption",
        f"{industry} {geography} annual sales shipments transactions consumption",
        f"{industry} {geography} average selling price pricing customer spending ARPU",
        f"{industry} {geography} suppliers production capacity utilisation",
        f"{industry} {geography} market data 2021 2022 2023 2024 2025",
        f"{industry} {geography} customer segments applications demand drivers spending",
        f"{industry} {geography} official statistics industry association company annual report",
    ]


def search_market(industry, geography):
    """Run baseline market research and return structured source records."""
    print(f"Researching {industry} in {geography}...")
    sources = _run_search_queries(
        build_research_queries(industry, geography),
        max_results=4,
    )

    tier_counts = {}
    for source in sources:
        tier = source.get("source_tier", "Unverified")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    print(f"Found {len(sources)} unique sources.")
    print("Source mix:", tier_counts)
    return sources


def search_research_gaps(gaps, industry, geography):
    """
    Research data gaps with direct-data, published-source and proxy searches.
    Accepts either strings or dictionaries from the assessment output.
    """
    if not gaps:
        return []

    queries = []
    for gap in gaps:
        if isinstance(gap, dict):
            gap_text = (
                gap.get("description")
                or gap.get("variable")
                or gap.get("gap")
                or str(gap)
            )
        else:
            gap_text = str(gap)

        gap_text = re.sub(r"\s+", " ", gap_text).strip()
        if not gap_text:
            continue

        queries.extend([
            f"{industry} {geography} {gap_text} official data statistics",
            f"{industry} {geography} {gap_text} annual report industry association",
            f"{industry} {geography} {gap_text} proxy alternative indicator estimate",
        ])

    sources = _run_search_queries(queries[:15], max_results=3)
    print(f"Additional gap research found {len(sources)} unique sources.")
    return sources


if __name__ == "__main__":
    # Quick classification checks; no web search required.
    test_urls = [
        "https://media.atherenergy.com/Ather-Energy-Industry-Report.pdf",
        "https://www.kenresearch.com/industry-reports/india-electric-two-wheeler-market",
        "https://www.morth.nic.in/",
        "https://example-unknown-company.com/",
    ]

    print("Classification smoke test:")
    for test_url in test_urls:
        print(classify_source(test_url), "|", test_url)
