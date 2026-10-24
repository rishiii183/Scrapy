"""
Google Maps Extraction Engine (Milestone 1 - Agent 1)

Components:
- browser_manager: Anti-bot Playwright Chrome lifecycle management
- filters: Custom domain exclusions and social/directory qualification
- normalizer: 10-digit phone cleaner, address/ZIP centroid mapper, specialty classifier
- query_catalog: Pre-seeded geographic queries across TX, FL, OH, GA, AZ
- maps_extractor: Google Maps DOM feed scrolling, parsing, and lead generation
"""

from src.scraper.filters import (
    is_social_or_directory,
    is_custom_domain,
    is_no_website,
    is_qualified_lead_website,
    classify_website,
    SOCIAL_AND_DIRECTORIES,
)
from src.scraper.normalizer import (
    clean_phone_10digit,
    format_phone_display,
    normalize_business_name,
    parse_address,
    classify_specialty,
    classify_specialty_key,
    get_dedup_key,
    MUNICIPAL_CENTROIDS,
)
from src.scraper.query_catalog import (
    TargetQuery,
    TARGET_QUERIES,
    get_all_queries,
    get_queries_by_state,
    get_default_query_catalog,
    generate_queries_for_niche,
)
try:
    from src.scraper.browser_manager import BrowserManager
    from src.scraper.maps_extractor import GoogleMapsExtractor
except ImportError:
    BrowserManager = None  # type: ignore
    GoogleMapsExtractor = None  # type: ignore

__all__ = [
    "BrowserManager",
    "GoogleMapsExtractor",
    "TargetQuery",
    "TARGET_QUERIES",
    "get_all_queries",
    "get_queries_by_state",
    "get_default_query_catalog",
    "generate_queries_for_niche",
    "is_social_or_directory",
    "is_custom_domain",
    "is_no_website",
    "is_qualified_lead_website",
    "classify_website",
    "SOCIAL_AND_DIRECTORIES",
    "clean_phone_10digit",
    "format_phone_display",
    "normalize_business_name",
    "parse_address",
    "classify_specialty",
    "classify_specialty_key",
    "get_dedup_key",
    "MUNICIPAL_CENTROIDS",
]
