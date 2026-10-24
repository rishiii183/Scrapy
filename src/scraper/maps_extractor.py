"""
Google Maps Extraction Engine (Milestone 1 - Agent 1).

Orchestrates:
- Playwright browser interaction with Google Maps
- Feed scrolling and dynamic card loading
- Card DOM parsing (business name, rating, reviews, phone, address)
- Strict website qualification (excludes custom domains, captures no-website and social profiles)
- Trade specialty classification and municipal centroid fallbacks
- Deduplication and priority scoring (>10 reviews = 🔥 High)
"""

import logging
import re
from typing import Dict, List, Optional, Set
from playwright.sync_api import Page, Locator

from src.config import (
    DEFAULT_SCROLL_COUNT,
    SCROLL_PAUSE_SECONDS,
    PAGE_LOAD_TIMEOUT_MS,
    HIGH_PRIORITY_REVIEW_THRESHOLD,
    MAPS_BASE_URL,
)
from src.models import RawLead, QualifiedLead
from src.scraper.browser_manager import BrowserManager
from src.scraper.filters import classify_website, is_custom_domain
from src.scraper.normalizer import (
    clean_phone_10digit,
    format_phone_display,
    parse_address,
    classify_specialty,
    get_dedup_key,
)
from src.scraper.query_catalog import TargetQuery, get_default_query_catalog, get_all_queries

logger = logging.getLogger(__name__)


class GoogleMapsExtractor:
    """
    Core extraction engine for discovering roofing contractors without websites on Google Maps.
    """

    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager

    @staticmethod
    def parse_card_data(
        card_text: str,
        anchor_aria_label: str = "",
        website_href: Optional[str] = None,
        place_href: str = "",
        default_city: str = "",
        default_state: str = "",
        search_query: Optional[str] = None,
        niche: str = "roofing",
        filter_mode: str = "missing_website",
    ) -> Optional[QualifiedLead]:
        """
        Pure extraction and classification logic for a single Google Maps result card.
        Strictly filters out contractors based on configurable filter_mode.
        Returns QualifiedLead if qualified; returns None if excluded or invalid.
        """
        # 1. Business Name
        business_name = anchor_aria_label.strip()
        if not business_name:
            lines = [l.strip() for l in card_text.split("\n") if l.strip()]
            business_name = lines[0] if lines else ""

        if not business_name:
            return None

        # 2. Strict Website Filtering
        is_qualified, website_status, clean_website_url = classify_website(website_href, filter_mode=filter_mode)
        if not is_qualified:
            # Discard any contractor with a custom domain
            return None

        # 3. Phone Number Extraction
        phone_match = re.search(
            r"(\+?1?[-.\s]?\(?[2-9][0-9]{2}\)?[-.\s]?[2-9][0-9]{2}[-.\s]?[0-9]{4})",
            card_text,
        )
        raw_phone = phone_match.group(1).strip() if phone_match else None
        cleaned_phone = clean_phone_10digit(raw_phone) or ""
        phone_display = format_phone_display(cleaned_phone or raw_phone)

        # 4. Star Rating and Review Count
        star_rating = 0.0
        review_count = 0
        rating_match = re.search(
            r"([1-5]\.[0-9])(?:\s*(?:stars?|★))?\s*(?:\(?\s*([0-9,]+)\+?(?:\s*reviews?)?\s*\)?)?",
            card_text,
            re.IGNORECASE,
        )
        if rating_match:
            try:
                star_rating = float(rating_match.group(1))
            except (ValueError, TypeError):
                star_rating = 0.0
            if rating_match.group(2):
                try:
                    review_count = int(rating_match.group(2).replace(",", ""))
                except (ValueError, TypeError):
                    review_count = 0

        # Alternate check for explicit review mentions (e.g. "45 reviews" or "(45 reviews)")
        # Standalone numbers in parentheses like "(903)" MUST NOT match as they represent phone area codes
        if review_count == 0:
            rev_match = re.search(r"\b([0-9,]+)\s+reviews?\b", card_text, re.IGNORECASE)
            if rev_match:
                try:
                    review_count = int(rev_match.group(1).replace(",", ""))
                except (ValueError, TypeError):
                    pass

        # 5. Address Parsing with Municipal Centroid Fallback
        lines = [l.strip() for l in card_text.split("\n") if l.strip()]
        addr_line = None
        for line in lines:
            if re.search(r"\b[0-9]{1,5}\s+[A-Za-z0-9\s.,#-]+", line) and not line.startswith("+1"):
                addr_line = line
                break

        city, state, zip_code = parse_address(addr_line, default_city=default_city, default_state=default_state)

        # 6. Trade Specialty Classification
        specialty = classify_specialty(business_name, card_text, niche=niche)

        # 7. Priority Assignment
        priority = "🔥 High" if review_count > HIGH_PRIORITY_REVIEW_THRESHOLD else "⚡ Medium"

        raw_lead = RawLead(
            business_name=business_name,
            cleaned_phone=cleaned_phone,
            phone_display=phone_display,
            city=city,
            state=state,
            zip_code=zip_code,
            review_count=review_count,
            star_rating=star_rating,
            specialty=specialty,
            website_status=website_status,
            website_url=clean_website_url,
            place_url=place_href or "",
        )

        return QualifiedLead.from_raw(raw_lead, priority=priority, search_query=search_query)

    def extract_from_card_locator(
        self,
        card: Locator,
        default_city: str,
        default_state: str,
        search_query: Optional[str] = None,
        niche: str = "roofing",
        filter_mode: str = "missing_website",
    ) -> Optional[QualifiedLead]:
        """Extract lead from a live Playwright card Locator."""
        card_text = card.inner_text().strip()
        if not card_text:
            return None

        anchor = card.locator("a.hfpxzc")
        anchor_aria_label = ""
        place_href = ""
        if anchor.count() > 0:
            anchor_aria_label = anchor.first.get_attribute("aria-label") or ""
            place_href = anchor.first.get_attribute("href") or ""

        # Website element detection
        web_link = card.locator('a[data-value="Website"], a[aria-label*="website" i]')
        website_href = None
        if web_link.count() > 0:
            website_href = web_link.first.get_attribute("href")

        if niche == "roofing" and filter_mode == "missing_website":
            return self.parse_card_data(
                card_text=card_text,
                anchor_aria_label=anchor_aria_label,
                website_href=website_href,
                place_href=place_href,
                default_city=default_city,
                default_state=default_state,
                search_query=search_query,
            )
        return self.parse_card_data(
            card_text=card_text,
            anchor_aria_label=anchor_aria_label,
            website_href=website_href,
            place_href=place_href,
            default_city=default_city,
            default_state=default_state,
            search_query=search_query,
            niche=niche,
            filter_mode=filter_mode,
        )

    def extract_for_query(
        self,
        target: TargetQuery,
        max_scrolls: int = DEFAULT_SCROLL_COUNT,
        page: Optional[Page] = None,
        niche: str = "roofing",
        filter_mode: str = "missing_website",
    ) -> List[QualifiedLead]:
        """
        Run Google Maps search for a TargetQuery, scroll feed, and return qualified leads.
        """
        results: List[QualifiedLead] = []
        should_close_page = False

        if page is None:
            if self.browser_manager is None:
                self.browser_manager = BrowserManager()
            page = self.browser_manager.new_page()
            should_close_page = True

        try:
            search_url = f"{MAPS_BASE_URL}{target.query.replace(' ', '+')}"
            logger.info("Navigating to: %s", search_url)

            page.goto(search_url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            feed = page.locator('div[role="feed"]')
            if feed.count() == 0:
                logger.warning("No feed element found for query: %s", target.query)
                return results

            # Scroll feed to hydrate dynamic business cards
            for s in range(max_scrolls):
                feed.evaluate("el => el.scrollBy(0, 1500)")
                page.wait_for_timeout(int(SCROLL_PAUSE_SECONDS * 1000))

            cards = page.locator('div[role="feed"] > div > div[jsaction]')
            count = cards.count()
            logger.info("Found %d cards in feed for %s", count, target.query)

            for i in range(count):
                card = cards.nth(i)
                if niche == "roofing" and filter_mode == "missing_website":
                    lead = self.extract_from_card_locator(
                        card,
                        default_city=target.city,
                        default_state=target.state,
                        search_query=target.query,
                    )
                else:
                    lead = self.extract_from_card_locator(
                        card,
                        default_city=target.city,
                        default_state=target.state,
                        search_query=target.query,
                        niche=niche,
                        filter_mode=filter_mode,
                    )
                if lead:
                    results.append(lead)

        finally:
            if should_close_page and page:
                try:
                    page.close()
                except Exception:
                    pass

        return results

    def extract_multi_queries(
        self,
        queries: List[TargetQuery],
        max_scrolls: int = DEFAULT_SCROLL_COUNT,
        target_count: int = 25,
        niche: str = "roofing",
        filter_mode: str = "missing_website",
    ) -> List[QualifiedLead]:
        """
        Orchestrate multiple geographic searches until target_count unique leads are gathered.
        Enforces cross-query deduplication.
        """
        all_leads: List[QualifiedLead] = []
        seen_keys: Set[str] = set()

        close_manager = False
        if self.browser_manager is None:
            self.browser_manager = BrowserManager()
            self.browser_manager.start()
            close_manager = True

        try:
            page = self.browser_manager.new_page()
            try:
                for target in queries:
                    if len(all_leads) >= target_count:
                        break

                    if niche == "roofing" and filter_mode == "missing_website":
                        leads = self.extract_for_query(
                            target,
                            max_scrolls=max_scrolls,
                            page=page,
                        )
                    else:
                        leads = self.extract_for_query(
                            target,
                            max_scrolls=max_scrolls,
                            page=page,
                            niche=niche,
                            filter_mode=filter_mode,
                        )
                    for lead in leads:
                        d_key = lead.dedup_key
                        if d_key in seen_keys:
                            continue
                        seen_keys.add(d_key)
                        all_leads.append(lead)
                        if len(all_leads) >= target_count:
                            break
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        finally:
            if close_manager and self.browser_manager:
                self.browser_manager.close()
                self.browser_manager = None

        return all_leads

    def run_sample_extraction(
        self,
        target_count: int = 25,
        niche: str = "roofing",
        filter_mode: str = "missing_website",
    ) -> List[QualifiedLead]:
        """
        Run multi-state extraction across target US states (TX, FL, OH, GA, AZ)
        to extract verified qualified leads meeting all acceptance criteria.
        """
        queries = get_default_query_catalog(niche=niche)
        # If default set doesn't yield enough, fall back to all queries
        leads = self.extract_multi_queries(
            queries,
            target_count=target_count,
            niche=niche,
            filter_mode=filter_mode,
        )
        if len(leads) < target_count:
            all_q = get_all_queries(niche=niche)
            remaining = [q for q in all_q if q not in queries]
            more_leads = self.extract_multi_queries(
                remaining,
                target_count=target_count - len(leads),
                niche=niche,
                filter_mode=filter_mode,
            )
            for l in more_leads:
                if l.dedup_key not in {x.dedup_key for x in leads}:
                    leads.append(l)
        return leads
