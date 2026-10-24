import json
import urllib.request
import re

TOKEN_PATH = r"C:\Users\rishi\.gemini\antigravity\plugin_data\gsheets\token.json"
SPREADSHEET_ID = "12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY"

def normalize_name(name: str) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r"\s*&\s*", " and ", n)
    n = re.sub(r"[^\w\s]", "", n)
    n = re.sub(r"^the\s+", "", n)
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
    n = re.sub(r"\b(and|or|of)\b$", "", n).strip()
    return re.sub(r"\s+", " ", n).strip()

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else digits

def load_existing_crm_index():
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        token = json.load(f)["token"]["access_token"]
    
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Leads%20Tracker!A1:U50"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    rows = data.get("values", [])
    headers = rows[0]
    leads = rows[1:]
    
    existing_phones = set()
    existing_names = set()
    indexed_records = []
    
    for idx, row in enumerate(leads, start=2):
        # Company Name is Col C (index 2)
        company = row[2] if len(row) > 2 else ""
        # Work Email is Col J (index 9) - might contain phone e.g. "Call: (214) 713-2050"
        work_email = row[9] if len(row) > 9 else ""
        # Notes & Next Steps is Col U (index 20) - contains "Phone: (XXX) XXX-XXXX"
        notes = row[20] if len(row) > 20 else ""
        
        # Extract phone from notes or work_email
        phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", notes + " " + work_email)
        phone_str = phone_match.group(0) if phone_match else ""
        
        norm_name = normalize_name(company)
        norm_phone = normalize_phone(phone_str)
        
        if norm_name:
            existing_names.add(norm_name)
        if norm_phone:
            existing_phones.add(norm_phone)
            
        indexed_records.append({
            "row": idx,
            "company": company,
            "norm_name": norm_name,
            "phone": phone_str,
            "norm_phone": norm_phone
        })
        
    return existing_names, existing_phones, indexed_records

if __name__ == "__main__":
    names, phones, records = load_existing_crm_index()
    print(f"Total existing records indexed: {len(records)}")
    print(f"Unique normalized names: {len(names)}")
    print(f"Unique normalized phones: {len(phones)}")
    print("\nSample Indexed Entries:")
    for r in records[:5]:
        print(f"Row {r['row']}: '{r['norm_name']}' | Phone: {r['norm_phone']}")
