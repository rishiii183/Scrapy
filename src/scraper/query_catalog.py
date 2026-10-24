"""
Target Query Catalog for Multi-State Google Maps Extraction.

Defines targeted geographic queries across tier-2 and tier-3 US metro areas:
- Texas (TX): Tyler, Longview, Lubbock, Abilene, Waco, Midland
- Florida (FL): Ocala, Gainesville, Pensacola, Lakeland, Panama City, Fort Pierce
- Ohio (OH): Canton, Akron, Youngstown, Mansfield, Lima, Springfield
- Georgia (GA): Macon, Warner Robins, Augusta, Columbus, Albany, Valdosta
- Arizona (AZ): Flagstaff, Prescott, Yuma, Lake Havasu City, Sierra Vista, Casa Grande
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TargetQuery(BaseModel):
    """Geographic search query specification for Google Maps."""
    query: str = Field(..., description="Full search term sent to Google Maps")
    city: str = Field(..., description="Target municipal city")
    state: str = Field(..., description="Two-letter US state code")
    default_zip: str = Field(..., description="Default municipal centroid ZIP code")
    market_tier: str = Field(default="tier-2", description="Market category tier")


TARGET_QUERIES: List[TargetQuery] = [
    # --- Texas (TX) ---
    TargetQuery(
        query="roofing contractors Tyler TX",
        city="Tyler",
        state="TX",
        default_zip="75701",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofing companies Longview TX",
        city="Longview",
        state="TX",
        default_zip="75601",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roof repair contractor Lubbock TX",
        city="Lubbock",
        state="TX",
        default_zip="79401",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofers Abilene TX",
        city="Abilene",
        state="TX",
        default_zip="79601",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="residential roofing contractors Waco TX",
        city="Waco",
        state="TX",
        default_zip="76701",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="commercial roofing contractors Midland TX",
        city="Midland",
        state="TX",
        default_zip="79701",
        market_tier="tier-2",
    ),

    # --- Florida (FL) ---
    TargetQuery(
        query="roofing contractor Ocala FL",
        city="Ocala",
        state="FL",
        default_zip="34471",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roof repair contractor Gainesville FL",
        city="Gainesville",
        state="FL",
        default_zip="32601",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofers Pensacola FL",
        city="Pensacola",
        state="FL",
        default_zip="32501",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofing companies Lakeland FL",
        city="Lakeland",
        state="FL",
        default_zip="33801",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="storm roof repair Panama City FL",
        city="Panama City",
        state="FL",
        default_zip="32401",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="roofing services Fort Pierce FL",
        city="Fort Pierce",
        state="FL",
        default_zip="34950",
        market_tier="tier-3",
    ),

    # --- Ohio (OH) ---
    TargetQuery(
        query="roof repair contractor Canton OH",
        city="Canton",
        state="OH",
        default_zip="44702",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofing companies Akron OH",
        city="Akron",
        state="OH",
        default_zip="44308",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofers Youngstown OH",
        city="Youngstown",
        state="OH",
        default_zip="44503",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofing contractor Mansfield OH",
        city="Mansfield",
        state="OH",
        default_zip="44902",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="storm restoration roofing Lima OH",
        city="Lima",
        state="OH",
        default_zip="45801",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="roof repair Springfield OH",
        city="Springfield",
        state="OH",
        default_zip="45502",
        market_tier="tier-3",
    ),

    # --- Georgia (GA) ---
    TargetQuery(
        query="roofers Macon GA",
        city="Macon",
        state="GA",
        default_zip="31201",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofing contractor Warner Robins GA",
        city="Warner Robins",
        state="GA",
        default_zip="31088",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="roof repair Augusta GA",
        city="Augusta",
        state="GA",
        default_zip="30901",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roofing companies Columbus GA",
        city="Columbus",
        state="GA",
        default_zip="31901",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="residential roofing Albany GA",
        city="Albany",
        state="GA",
        default_zip="31701",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="roofing services Valdosta GA",
        city="Valdosta",
        state="GA",
        default_zip="31601",
        market_tier="tier-3",
    ),

    # --- Arizona (AZ) ---
    TargetQuery(
        query="roofing contractors Flagstaff AZ",
        city="Flagstaff",
        state="AZ",
        default_zip="86001",
        market_tier="tier-2",
    ),
    TargetQuery(
        query="roof repair Prescott AZ",
        city="Prescott",
        state="AZ",
        default_zip="86301",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="roofing companies Yuma AZ",
        city="Yuma",
        state="AZ",
        default_zip="85364",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="roofers Lake Havasu City AZ",
        city="Lake Havasu City",
        state="AZ",
        default_zip="86403",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="residential roofing Sierra Vista AZ",
        city="Sierra Vista",
        state="AZ",
        default_zip="85635",
        market_tier="tier-3",
    ),
    TargetQuery(
        query="roof repair Casa Grande AZ",
        city="Casa Grande",
        state="AZ",
        default_zip="85122",
        market_tier="tier-3",
    ),
]

METRO_MARKETS_BY_STATE = {
    "TX": [
        ("Tyler", "75701", "tier-2"),
        ("Longview", "75601", "tier-2"),
        ("Lubbock", "79401", "tier-2"),
        ("Abilene", "79601", "tier-3"),
        ("Waco", "76701", "tier-2"),
        ("Midland", "79701", "tier-2"),
        ("Dallas", "75201", "tier-1"),
        ("Houston", "77001", "tier-1"),
        ("Austin", "78701", "tier-1"),
        ("San Antonio", "78201", "tier-1"),
    ],
    "FL": [
        ("Ocala", "34471", "tier-2"),
        ("Gainesville", "32601", "tier-2"),
        ("Pensacola", "32501", "tier-2"),
        ("Lakeland", "33801", "tier-2"),
        ("Panama City", "32401", "tier-3"),
        ("Fort Pierce", "34950", "tier-3"),
        ("Orlando", "32801", "tier-1"),
        ("Tampa", "33601", "tier-1"),
        ("Miami", "33101", "tier-1"),
        ("Jacksonville", "32099", "tier-1"),
    ],
    "OH": [
        ("Canton", "44702", "tier-2"),
        ("Akron", "44308", "tier-2"),
        ("Youngstown", "44503", "tier-2"),
        ("Mansfield", "44902", "tier-3"),
        ("Lima", "45801", "tier-3"),
        ("Springfield", "45502", "tier-3"),
        ("Columbus", "43201", "tier-1"),
        ("Cleveland", "44101", "tier-1"),
        ("Cincinnati", "45201", "tier-1"),
    ],
    "GA": [
        ("Macon", "31201", "tier-2"),
        ("Warner Robins", "31088", "tier-3"),
        ("Augusta", "30901", "tier-2"),
        ("Columbus", "31901", "tier-2"),
        ("Albany", "31701", "tier-3"),
        ("Valdosta", "31601", "tier-3"),
        ("Atlanta", "30303", "tier-1"),
        ("Savannah", "31401", "tier-2"),
    ],
    "AZ": [
        ("Flagstaff", "86001", "tier-2"),
        ("Prescott", "86301", "tier-3"),
        ("Yuma", "85364", "tier-3"),
        ("Lake Havasu City", "86403", "tier-3"),
        ("Sierra Vista", "85635", "tier-3"),
        ("Casa Grande", "85122", "tier-3"),
        ("Phoenix", "85001", "tier-1"),
        ("Tucson", "85701", "tier-1"),
        ("Mesa", "85201", "tier-1"),
    ],
    "CA": [
        ("Los Angeles", "90001", "tier-1"),
        ("San Diego", "92101", "tier-1"),
        ("San Jose", "95101", "tier-1"),
        ("Sacramento", "95814", "tier-2"),
        ("Fresno", "93701", "tier-2"),
    ],
    "NY": [
        ("New York", "10001", "tier-1"),
        ("Buffalo", "14201", "tier-2"),
        ("Rochester", "14601", "tier-2"),
        ("Syracuse", "13201", "tier-2"),
        ("Albany", "12201", "tier-2"),
    ],
    "NC": [
        ("Charlotte", "28201", "tier-1"),
        ("Raleigh", "27601", "tier-1"),
        ("Greensboro", "27401", "tier-2"),
        ("Durham", "27701", "tier-2"),
    ],
    "IL": [
        ("Chicago", "60601", "tier-1"),
        ("Aurora", "60505", "tier-2"),
        ("Naperville", "60540", "tier-2"),
        ("Rockford", "61101", "tier-2"),
    ],
    "PA": [
        ("Philadelphia", "19101", "tier-1"),
        ("Pittsburgh", "15201", "tier-1"),
        ("Allentown", "18101", "tier-2"),
        ("Erie", "16501", "tier-2"),
    ],
}


def generate_queries_for_niche(
    niche: str = "roofing",
    states: Optional[List[str]] = None,
    cities: Optional[List[tuple]] = None,
    query_formats: Optional[List[str]] = None,
) -> List[TargetQuery]:
    """
    Generate dynamic geographic search queries for any niche and geographic targets.
    
    Args:
        niche: Business category or trade (e.g. 'plumber', 'roofing', 'HVAC', 'dentist')
        states: Optional list of 2-letter state codes (defaults to TX, FL, OH, GA, AZ)
        cities: Optional list of (city_name, state_code, default_zip, tier) tuples
        query_formats: Optional list of format strings like '{niche} contractors {city} {state}'
    """
    clean_niche = niche.strip().lower()
    if clean_niche in ("roofing", "roofer", "roofers") and not states and not cities and not query_formats:
        return list(TARGET_QUERIES)

    target_states = [s.strip().upper() for s in (states or ["TX", "FL", "OH", "GA", "AZ"])]
    formats = query_formats or [
        "{niche} contractors {city} {state}",
        "{niche} companies {city} {state}",
        "{niche} services {city} {state}",
        "{niche} repair {city} {state}",
    ]

    generated: List[TargetQuery] = []
    seen_queries = set()

    if cities:
        for item in cities:
            city_name = item[0]
            st = item[1].upper()
            zip_c = item[2] if len(item) > 2 else "00000"
            tier = item[3] if len(item) > 3 else "tier-2"
            for fmt in formats:
                q_text = fmt.format(niche=clean_niche, city=city_name, state=st)
                if q_text not in seen_queries:
                    seen_queries.add(q_text)
                    generated.append(
                        TargetQuery(
                            query=q_text,
                            city=city_name,
                            state=st,
                            default_zip=zip_c,
                            market_tier=tier,
                        )
                    )
        return generated

    for st in target_states:
        metros = METRO_MARKETS_BY_STATE.get(st, [(f"Central {st}", "00000", "tier-2")])
        for c_info in metros:
            city_name = c_info[0]
            zip_c = c_info[1]
            tier = c_info[2] if len(c_info) > 2 else "tier-2"
            # Generate 1-2 diverse queries per metro to balance breadth
            for fmt in formats[:2]:
                q_text = fmt.format(niche=clean_niche, city=city_name, state=st)
                if q_text not in seen_queries:
                    seen_queries.add(q_text)
                    generated.append(
                        TargetQuery(
                            query=q_text,
                            city=city_name,
                            state=st,
                            default_zip=zip_c,
                            market_tier=tier,
                        )
                    )

    return generated


def get_all_queries(niche: Optional[str] = None) -> List[TargetQuery]:
    """Retrieve all configured geographic search queries, optionally for a specific niche."""
    if niche and niche.strip().lower() not in ("roofing", "roofer", "roofers"):
        return generate_queries_for_niche(niche=niche)
    return list(TARGET_QUERIES)


def get_queries_by_state(state: str, niche: Optional[str] = None) -> List[TargetQuery]:
    """Filter search queries by 2-letter state code and optional niche."""
    st = state.strip().upper()
    if niche and niche.strip().lower() not in ("roofing", "roofer", "roofers"):
        return generate_queries_for_niche(niche=niche, states=[st])
    return [q for q in TARGET_QUERIES if q.state == st]


def get_default_query_catalog(niche: Optional[str] = None) -> List[TargetQuery]:
    """Returns the primary 5-state multi-state exploration query set (1 per state)."""
    if niche and niche.strip().lower() not in ("roofing", "roofer", "roofers"):
        all_q = generate_queries_for_niche(niche=niche)
        seen_states = set()
        primary = []
        for q in all_q:
            if q.state not in seen_states:
                seen_states.add(q.state)
                primary.append(q)
        return primary

    seen_states = set()
    primary = []
    for q in TARGET_QUERIES:
        if q.state not in seen_states:
            seen_states.add(q.state)
            primary.append(q)
    return primary
