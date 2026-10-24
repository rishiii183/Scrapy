"""
Website Filtering and Domain Classification Engine.

Implements strict website qualification rules:
1. Contractors with NO website -> QUALIFIED ("None (No Website)")
2. Contractors with ONLY social/directory profiles -> QUALIFIED ("None (No Website - Social Only)")
3. Contractors with custom domains (.com, .io, .net, .co, .org, etc.) -> DISQUALIFIED
"""

import re
from typing import Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

# Whitelist of social networks, consumer directories, and listing platforms
SOCIAL_AND_DIRECTORIES: Set[str] = {
    # Social Platforms
    "facebook.com",
    "m.facebook.com",
    "fb.com",
    "fb.me",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "youtube.com",
    "pinterest.com",
    # Directories & Contractor Portals
    "yelp.com",
    "bbb.org",
    "yellowpages.com",
    "angi.com",
    "angieslist.com",
    "homeadvisor.com",
    "thumbtack.com",
    "houzz.com",
    "nextdoor.com",
    "manta.com",
    "mapquest.com",
    "superpages.com",
    "chamberofcommerce.com",
    "porch.com",
    "buildzoom.com",
    "dandb.com",
    "expertise.com",
    "bark.com",
    "cylex.us.com",
    "cylex-usa.com",
    "alignable.com",
    "patch.com",
    "local.yahoo.com",
    "citysearch.com",
    "merchantcircle.com",
    "ezlocal.com",
    "yellowbook.com",
    "whitepages.com",
    "dexknows.com",
    "kudzu.com",
    "judysbook.com",
    "google.com",
    "business.site",
}


def clean_url_scheme(url: str) -> str:
    """Ensure URL has a parseable scheme for urlparse."""
    url = url.strip()
    lower_url = url.lower()
    if not (lower_url.startswith("http://") or lower_url.startswith("https://") or lower_url.startswith("//")):
        url = "https://" + url
    elif url.startswith("//"):
        url = "https:" + url
    return url


def unwrap_redirector_target(url: Optional[str]) -> Optional[str]:
    """
    If URL is an outbound wrapper redirector (Google, Facebook, YouTube, LinkedIn),
    extract and return the embedded destination URL if present.
    """
    if not url or not url.strip():
        return None
    curr_url = url.strip()
    depth = 0
    while depth < 5:
        depth += 1
        try:
            parsed = urlparse(clean_url_scheme(curr_url))
            hostname = (parsed.hostname or "").lower()
            if any(wrapper in hostname for wrapper in ["google.com", "facebook.com", "youtube.com", "linkedin.com"]):
                qs = parse_qs(parsed.query)
                unwrapped = None
                for key in ["q", "u", "url"]:
                    if key in qs and qs[key]:
                        cand = unquote(qs[key][0]).strip()
                        if cand.lower().startswith(("http://", "https://", "//")):
                            unwrapped = cand
                            break
                if unwrapped and unwrapped != curr_url:
                    curr_url = unwrapped
                    continue
        except Exception:
            pass
        break
    return curr_url if curr_url != url.strip() else None


def extract_domain(url: Optional[str]) -> str:
    """
    Extract the normalized lowercase hostname from a URL.
    Strips 'www.' and any port numbers.
    Unwraps outbound redirectors if present.
    """
    if not url or not url.strip():
        return ""
    try:
        target = unwrap_redirector_target(url)
        clean = clean_url_scheme(target or url)
        parsed = urlparse(clean)
        hostname = (parsed.hostname or "").lower()
        if hostname.startswith("www."):
            hostname = hostname[4:]
        return hostname
    except Exception:
        return ""


def is_no_website(url: Optional[str]) -> bool:
    """
    Check if the website field represents an absent website.
    Handles None, empty string, or Google Maps UI placeholders.
    """
    if url is None:
        return True
    val = url.strip().lower()
    if not val:
        return True
    if val in {"none", "n/a", "no website", "add website", "null", "undefined"}:
        return True
    return False


def is_social_or_directory(url: Optional[str]) -> bool:
    """
    Check if the URL belongs to a known social media or business directory platform.
    Matches exact domain or root subdomain (e.g. m.facebook.com -> facebook.com).
    """
    if not url:
        return False
    domain = extract_domain(url)
    if not domain:
        return False

    for target in SOCIAL_AND_DIRECTORIES:
        if domain == target or domain.endswith("." + target):
            return True
    return False


def is_custom_domain(url: Optional[str]) -> bool:
    """
    Return True if the URL points to a custom domain (i.e. not empty and not social/directory).
    These businesses must be strictly excluded from outreach.
    """
    if is_no_website(url):
        return False
    return not is_social_or_directory(url)


def is_qualified_lead_website(url: Optional[str]) -> bool:
    """
    Core filter: Returns True if the contractor has NO website or ONLY a social/directory page.
    Returns False if they have an active custom domain (.com, .io, .net, etc.).
    """
    if is_no_website(url):
        return True
    return is_social_or_directory(url)


def classify_website(url: Optional[str]) -> Tuple[bool, str, Optional[str]]:
    """
    Classify a contractor's website link according to PROJECT.md interface contracts.
    
    Returns:
        (is_qualified, website_status, clean_url)
        - is_qualified: bool (True if candidate for outreach)
        - website_status: 'None (No Website)' or 'None (No Website - Social Only)' or 'Custom Website (<domain>)'
        - clean_url: sanitized URL or None
    """
    if is_no_website(url):
        return True, "None (No Website)", None

    clean_url = url.strip()
    target = unwrap_redirector_target(clean_url)
    effective_url = target if target else clean_url

    if is_social_or_directory(effective_url):
        return True, "None (No Website - Social Only)", effective_url

    domain = extract_domain(effective_url)
    return False, f"Custom Website ({domain})", clean_url
