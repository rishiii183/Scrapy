import re

def normalize_name(name: str) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    # Replace & with and
    n = re.sub(r"\s*&\s*", " and ", n)
    # Remove punctuation
    n = re.sub(r"[^\w\s]", "", n)
    # Remove leading 'the '
    n = re.sub(r"^the\s+", "", n)
    
    # Strictly corporate entity suffixes: LLC, Inc, Corp, Ltd, Co, PLLC, LP, LLP
    entity_suffixes = [
        "incorporated", "corporation", "limited liability company",
        "limited liability partnership", "limited partnership",
        "limited", "company", "corp", "pllc", "llc", "llp", "inc", "ltd", "co"
    ]
    pattern = r"\b(" + "|".join(entity_suffixes) + r")\b$"
    while True:
        cleaned = re.sub(pattern, "", n).strip()
        if cleaned == n or not cleaned:
            break
        n = cleaned
        
    # Strip any trailing conjunctions left dangling (e.g., 'and')
    n = re.sub(r"\b(and|or|of)\b$", "", n).strip()
    # Normalize multiple whitespace to single space
    n = re.sub(r"\s+", " ", n).strip()
    return n

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else digits

names = [
    "Guaranteed Roofing & Repairs",
    "TruGuard Roofing & Repairs",
    "MPC Roofing & Construction",
    "X Roof and Solar",
    "Devin Ishmael Roofing",
    "Coop's Roofing & Construction",
    "RM Roofing and Contracting LLC",
    "Reyes Roofing LLC",
    "Valley Rebuild LLC",
    "The Arizona Roofer",
    "East Houston Roofing Contractor",
    "Lifetime Roofing Company",
    # Edge test cases
    "Guaranteed Roofing and Repairs, LLC.",
    "The Guaranteed Roofing & Repairs",
    "MPC Roofing and Construction Inc.",
    "Reyes Roofing, L.L.C.",
]

print("=== Refined Business Name Normalization ===")
for name in names:
    print(f"{name:40} -> '{normalize_name(name)}'")
