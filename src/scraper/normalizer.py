"""
Data Normalization, Address Parsing, Phone Cleaning, and Trade Specialty Classification.

Provides:
- 10-digit E.164-compatible phone cleaner and display formatter
- Address parser with municipal centroid ZIP fallback for Service Area Businesses (SABs)
- Trade specialty classification (residential, commercial, storm repair, leak repair)
- Normalized business name deduplication key generator
"""

import re
from typing import Dict, Optional, Tuple

# Municipal Centroid ZIP Code lookup table for Service Area Businesses (SABs)
# Maps (city_lower, state_upper) -> 5-digit municipal centroid ZIP code
MUNICIPAL_CENTROIDS: Dict[Tuple[str, str], str] = {
    # Texas Metros
    ("tyler", "TX"): "75701",
    ("longview", "TX"): "75601",
    ("lubbock", "TX"): "79401",
    ("abilene", "TX"): "79601",
    ("waco", "TX"): "76701",
    ("midland", "TX"): "79701",
    ("odessa", "TX"): "79761",
    ("amarillo", "TX"): "79101",
    ("wichita falls", "TX"): "76301",
    ("dallas", "TX"): "75201",
    ("fort worth", "TX"): "76102",
    ("austin", "TX"): "78701",
    ("houston", "TX"): "77002",
    ("san antonio", "TX"): "78205",
    # Florida Metros
    ("ocala", "FL"): "34471",
    ("gainesville", "FL"): "32601",
    ("pensacola", "FL"): "32501",
    ("lakeland", "FL"): "33801",
    ("panama city", "FL"): "32401",
    ("fort pierce", "FL"): "34950",
    ("tampa", "FL"): "33602",
    ("orlando", "FL"): "32801",
    ("jacksonville", "FL"): "32202",
    ("tallahassee", "FL"): "32301",
    ("sarasota", "FL"): "34236",
    # Ohio Metros
    ("canton", "OH"): "44702",
    ("akron", "OH"): "44308",
    ("youngstown", "OH"): "44503",
    ("mansfield", "OH"): "44902",
    ("lima", "OH"): "45801",
    ("springfield", "OH"): "45502",
    ("cleveland", "OH"): "44114",
    ("columbus", "OH"): "43215",
    ("cincinnati", "OH"): "45202",
    ("dayton", "OH"): "45402",
    ("toledo", "OH"): "43604",
    # Georgia Metros
    ("macon", "GA"): "31201",
    ("warner robins", "GA"): "31088",
    ("augusta", "GA"): "30901",
    ("columbus", "GA"): "31901",
    ("albany", "GA"): "31701",
    ("valdosta", "GA"): "31601",
    ("savannah", "GA"): "31401",
    ("atlanta", "GA"): "30303",
    ("athens", "GA"): "30601",
    # Arizona Metros
    ("flagstaff", "AZ"): "86001",
    ("prescott", "AZ"): "86301",
    ("yuma", "AZ"): "85364",
    ("lake havasu city", "AZ"): "86403",
    ("sierra vista", "AZ"): "85635",
    ("casa grande", "AZ"): "85122",
    ("phoenix", "AZ"): "85001",
    ("tucson", "AZ"): "85701",
    ("mesa", "AZ"): "85201",
}

# State-level default centroid fallbacks if city is unlisted
STATE_CENTROID_DEFAULTS: Dict[str, str] = {
    "TX": "75701",
    "FL": "34471",
    "OH": "44702",
    "GA": "31201",
    "AZ": "86001",
}

US_STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def clean_phone_10digit(raw_phone: Optional[str]) -> Optional[str]:
    """
    Extract exactly 10 digits from a US phone string.
    - Strips 'tel:' URI prefix if present.
    - Rejects foreign country codes (+44, +49, +52, etc.); only allows +1 for NANP.
    - Strips extensions (ext, x, extension, #).
    - Strips leading country code '1' if 11 digits.
    - Enforces North American Numbering Plan (NANP) rules:
      Area code (first digit) must be in [2-9]
      Central office exchange code (fourth digit) must be in [2-9]
    Returns 10-digit string or None if invalid.
    """
    if not raw_phone:
        return None
    s = str(raw_phone).strip()
    if s.lower().startswith("tel:"):
        s = s[4:].strip()
    # Reject international numbers with + prefix other than +1 (US/NANP)
    if s.startswith("+") and not (s.startswith("+1") or s.startswith("+ 1")):
        return None
    # Strip extension patterns: ext., ext, x, extension, # followed by digits
    s = re.split(r"(?i)\s*(?:ext(?:ension)?\.?|x|#)\s*:?\s*\d+", s)[0]
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        # Enforce NANP area code and central office code rules: NXX-NXX-XXXX (N = 2-9)
        if digits[0] in "23456789" and digits[3] in "23456789":
            return digits
    return None


def format_phone_display(phone: Optional[str]) -> str:
    """
    Format phone number as standard US display: '(XXX) XXX-XXXX'.
    Accepts 10-digit strings or raw phone strings.
    """
    if not phone:
        return ""
    digits = clean_phone_10digit(phone)
    if digits:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    # Fallback to sanitized raw string if not 10 digits
    return str(phone).strip()


def parse_address(
    addr_str: Optional[str],
    default_city: str = "",
    default_state: str = "",
) -> Tuple[str, str, str]:
    """
    Parse address text into (city, state, zip_code).
    Handles standard US address lines and Service Area Businesses (SABs).
    Automatically supplies municipal centroid ZIP fallback if missing.
    """
    city = default_city.strip()
    state = default_state.strip().upper()
    zip_code = ""

    if addr_str:
        clean_addr = addr_str.strip()

        # 1. Extract 5-digit US ZIP code
        zip_match = re.search(r"\b([0-9]{5})(?:-[0-9]{4})?\b", clean_addr)
        if zip_match:
            zip_code = zip_match.group(1)

        # 2. Extract 2-letter state code preceding ZIP (e.g. 'TX 75703' or ', TX')
        state_match = re.search(r",\s*([A-Z]{2})\b(?:\s+[0-9]{5})?", clean_addr)
        if state_match:
            state = state_match.group(1).upper()
        else:
            # Check for spelled out state names
            for name, code in US_STATE_NAME_TO_CODE.items():
                if re.search(rf"\b{name}\b", clean_addr, re.IGNORECASE):
                    state = code
                    break

        # 3. Extract city name from comma-separated tokens
        parts = [p.strip() for p in clean_addr.split(",") if p.strip()]
        if len(parts) >= 3:
            # Format: 'Street, City, State ZIP, United States' -> parts[-3] is City
            candidate_city = parts[-3] if "united states" in parts[-1].lower() else parts[-2]
            # Strip digits and extra punctuation from candidate city
            candidate_city = re.sub(r"[0-9#]", "", candidate_city).strip()
            if candidate_city:
                city = candidate_city
        elif len(parts) == 2:
            # Format: 'Tyler, TX' or 'Tyler, TX 75701'
            candidate_city = re.sub(r"[0-9#]", "", parts[0]).strip()
            if candidate_city:
                city = candidate_city

    # 4. Fallback for ZIP code using municipal centroid table if empty
    if not zip_code:
        centroid_key = (city.lower(), state.upper())
        if centroid_key in MUNICIPAL_CENTROIDS:
            zip_code = MUNICIPAL_CENTROIDS[centroid_key]
        elif state.upper() in STATE_CENTROID_DEFAULTS:
            zip_code = STATE_CENTROID_DEFAULTS[state.upper()]
        else:
            zip_code = "00000"

    return city, state, zip_code


def classify_specialty_key(business_name: str, card_text: str = "") -> str:
    """
    Classify contractor into one of four standard keys:
    'commercial', 'storm repair', 'leak repair', or 'residential'.
    """
    combined = f"{business_name} {card_text}".lower()

    if any(k in combined for k in ["commercial", "tpo", "epdm", "flat roof", "industrial", "built-up", "pvc"]):
        return "commercial"
    elif any(k in combined for k in ["storm", "hail", "wind", "disaster", "restoration", "insurance claim", "tornado", "hurricane", "re-roof"]):
        return "storm repair"
    elif any(k in combined for k in ["leak", "emergency leak", "waterproofing", "patch", "flashing", "sealant"]):
        return "leak repair"
    else:
        return "residential"


def classify_specialty(business_name: str, card_text: str = "", niche: str = "roofing") -> str:
    """
    Return human-readable trade specialty display string matching PROJECT.md contracts.
    Supports roofing and any generic business niche.
    Examples:
    - 'Storm Damage & Re-roofing'
    - 'Commercial Roofing'
    - 'Emergency Leak Repair'
    - 'Residential Roofing'
    """
    n_lower = (niche or "roofing").strip().lower()

    if n_lower in ("roofing", "roofer", "roofers"):
        key = classify_specialty_key(business_name, card_text)
        mapping = {
            "storm repair": "Storm Damage & Re-roofing",
            "commercial": "Commercial Roofing",
            "leak repair": "Emergency Leak Repair",
            "residential": "Residential Roofing",
        }
        return mapping.get(key, "Residential Roofing")

    combined = f"{business_name} {card_text}".lower()

    if "plumb" in n_lower:
        if any(k in combined for k in ["drain", "sewer", "rooter", "clog"]):
            return "Drain Cleaning & Sewer Repair"
        elif any(k in combined for k in ["commercial", "industrial"]):
            return "Commercial Plumbing"
        elif any(k in combined for k in ["water heater", "boiler", "tankless"]):
            return "Water Heater & Boiler Repair"
        elif any(k in combined for k in ["leak", "emergency", "burst"]):
            return "Emergency Plumbing & Leak Detection"
        return "Residential Plumbing"

    elif "hvac" in n_lower or "air" in n_lower or "heating" in n_lower:
        if any(k in combined for k in ["commercial", "industrial"]):
            return "Commercial HVAC"
        elif any(k in combined for k in ["heating", "furnace", "heat pump"]):
            return "Heating & Furnace Repair"
        elif any(k in combined for k in ["emergency", "24/7", "urgent"]):
            return "Emergency AC & Heating Repair"
        return "Residential AC & HVAC"

    elif "electri" in n_lower:
        if any(k in combined for k in ["commercial", "industrial"]):
            return "Commercial Electrical"
        elif any(k in combined for k in ["emergency", "panel", "breaker"]):
            return "Emergency Electrical & Panel Upgrades"
        return "Residential Electrical Services"

    elif "dent" in n_lower:
        if any(k in combined for k in ["cosmetic", "implant", "veneer"]):
            return "Cosmetic & Implant Dentistry"
        elif any(k in combined for k in ["emergency", "urgent"]):
            return "Emergency Dental Care"
        return "General & Family Dentistry"

    # Generic niche classification
    if any(k in combined for k in ["commercial", "industrial"]):
        return f"Commercial {niche.title()}"
    elif any(k in combined for k in ["emergency", "urgent", "24/7"]):
        return f"Emergency {niche.title()}"
    return f"Residential {niche.title()}"


def normalize_business_name(name: str, niche: Optional[str] = None) -> str:
    """
    Normalize business name for deduplication:
    Strips legal entity types (LLC, PLLC, Inc, Co), trade words, punctuation, and extra whitespace.
    """
    if not name:
        return ""
    clean = name.lower()
    trade_words = r"\b(llc|pllc|inc|corp|corporation|co|ltd|company|roofing|construction|contractor|contracting|services|restoration|solutions"
    if niche and niche.strip():
        clean_n = re.escape(niche.strip().lower())
        trade_words += f"|{clean_n}"
    trade_words += r")\b"
    clean = re.sub(trade_words, "", clean)
    clean = re.sub(r"[^a-z0-9]", "", clean)
    return clean.strip()


def get_dedup_key(phone_10: Optional[str], business_name: str, state: str) -> str:
    """
    Generate an infallible deduplication key.
    Uses 10-digit phone number if present; otherwise normalized name + state.
    """
    if phone_10 and len(phone_10) == 10:
        return phone_10
    clean_name = normalize_business_name(business_name)
    return f"{clean_name}_{state.upper()}"
