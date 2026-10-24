"""
System Prompts and Jinja2 Templates for AI Personalization & Hook Generation.

Defines:
- LLM system instructions and few-shot examples enforcing strict invariants
- Deterministic Jinja2 templates for icebreakers, offer angles, email subjects,
  email bodies, and WhatsApp messages
- Invariant guarantees:
  * Sentence 1 references exact contractor city/metro and trade specialty
  * Sentence 2 highlights revenue lost to local competitors ranking on Google Maps
    and organic search for emergency roof repairs
  * Exactly 2 sentences in the icebreaker
  * Zero placeholder leakage
"""

from typing import List

SYSTEM_PROMPT_PERSONALIZER = """You are an elite B2B sales development copywriter specializing in outreach to commercial and residential roofing contractors.

Your task is to generate bespoke, hyper-personalized cold outreach assets for a roofing contractor who does not currently have an active website.

You MUST return valid JSON adhering strictly to the following schema:
{
  "icebreaker": "<2-sentence icebreaker>",
  "offer_angle": "<specific revenue pain point angle>",
  "staged_email_subject": "<cold email subject line>",
  "staged_email_body": "<cold email body copy>",
  "staged_whatsapp_msg": "<pre-formatted WhatsApp message>"
}

MANDATORY INVARIANTS:
1. ICEBREAKER STRUCTURE: Exactly TWO (2) complete sentences ending with periods.
   - Sentence 1: MUST explicitly reference the contractor's exact city/metro and trade specialty niche.
   - Sentence 2: MUST explicitly highlight revenue lost to local competitors ranking on Google Maps and organic search for emergency roof repairs (must contain 'lost' or 'missing out').
2. ZERO PLACEHOLDER LEAKAGE: Never leave unparsed tags like {{City}}, {{Name}}, {city}, or <Name>. Use the provided data or natural fallbacks like 'Team'.
3. EMAIL SUBJECT: Must mention the contractor's city and company name or trade specialty, and be at least 10 characters.
4. EMAIL BODY: Professional cold email containing the 2-sentence icebreaker and an invitation to view a quick 2-minute video.
5. WHATSAPP MESSAGE: Concise, punchy mobile text referencing the city, trade niche, competitor Google Maps rankings, and 2-min video offer.
"""

USER_PROMPT_TEMPLATE = """Generate personalized outreach copy for this contractor:
- Company Name: {{ company_name }}
- City: {{ city }}
- State: {{ state }}
- Trade Specialty: {{ specialty }}
- Contact Name: {{ contact_name }}
- Phone: {{ phone_display }}
"""

# Diverse deterministic Jinja2 templates ensuring 100% adherence to all invariants

ICEBREAKER_TEMPLATES: List[str] = [
    # Template 0
    "Came across {{ company_name }} while reviewing top-rated {{ specialty_lower }} contractors serving the {{ city }} area. "
    "With local competitors dominating Google Maps and organic search for {{ service_need }} in {{ city }}, "
    "your team is missing out on thousands in high-margin {{ service_call }} each month without a dedicated web presence.",

    # Template 1
    "Noticed {{ company_name }} while researching reputable {{ specialty_lower }} pros serving homeowners throughout {{ city }}. "
    "Local competitors are currently ranking ahead on Google Maps and organic search for {{ service_need }} in {{ city }}, "
    "causing high-margin repair and re-roof revenue to be lost each month without an official website.",

    # Template 2
    "Found {{ company_name }} while analyzing leading {{ specialty_lower }} specialists operating in {{ city }}. "
    "Without a dedicated site, top competitors ranking on Google Maps and organic search for {{ service_need }} in {{ city }} "
    "are capturing high-margin revenue that is lost each month to your business.",

    # Template 3
    "I was evaluating trusted {{ specialty_lower }} businesses across {{ city }} and came across {{ company_name }}. "
    "Local competitors dominating Google Maps and organic search for {{ service_need }} in {{ city }} "
    "are siphoning away high-dollar repair revenue that you are missing out on without a web presence.",
]

OFFER_ANGLE_TEMPLATES: List[str] = [
    "Capturing high-margin {{ service_need }} lost to local competitors ranking on Google Maps in {{ city }}.",
    "Reclaiming {{ service_need }} search volume and Google Maps rankings currently captured by competitors in {{ city }}.",
    "Emergency roof repair Google Maps search volume capture from local competitors in {{ city }}.",
    "Recovering high-ticket {{ service_need }} lost to competitors ranking on Google Maps in {{ city }}.",
]

EMAIL_SUBJECT_TEMPLATES: List[str] = [
    "{{ service_need_title }} inquiries in {{ city }} - {{ company_name }}",
    "Quick question regarding {{ service_need }} in {{ city }} for {{ company_name }}",
    "Google Maps emergency repair search traffic in {{ city }} - {{ company_name }}",
    "Missed {{ service_need }} in {{ city }} - {{ company_name }}",
]

EMAIL_BODY_TEMPLATES: List[str] = [
    """Hi {{ contact_name }},

{{ icebreaker }}

We put together a custom 2-minute video walking through the exact search keywords and Maps positions your competitors in {{ city }} are capturing, and how you can claim those emergency calls without high upfront costs.

Would you be open to a quick 2-min video showing how to capture this traffic?

Best regards,
{{ sender_team }}""",

    """Hi {{ contact_name }},

{{ icebreaker }}

Our team recorded a short 2-minute video breakdown detailing the specific emergency repair searches in {{ city }} currently going directly to your competitors, along with a simple strategy to start capturing them.

Would you be open to a quick 2-min video showing how to capture this traffic?

Best,
{{ sender_team }}""",
]

WHATSAPP_TEMPLATES: List[str] = [
    "Hi, saw your {{ specialty_lower }} work in {{ city }}. Competitors ranking on Google Maps for emergency repairs are capturing jobs without a website. Open to a 2-min video?",
    "Hello, noticed your {{ specialty_lower }} business in {{ city }}. Competitors ranking on Google Maps for {{ service_need }} are taking high-margin leads. Open to a 2-min video?",
    "Hi {{ contact_name }}, saw your {{ specialty_lower }} services in {{ city }}. Local competitors on Google Maps are dominating {{ service_need }} in {{ city }}. Would you be open to a 2-min video?",
]
