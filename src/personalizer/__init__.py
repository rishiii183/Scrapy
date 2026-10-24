"""
AI Personalization & Hook Generator Package (Milestone 3).

Exports:
- PersonalizerGenerator: High-level orchestration for single and batch draft generation
- TemplateEngine: Deterministic Jinja2 engine with diverse templates and 0% placeholder leakage
- LLMEngine: Multi-provider LLM adapter with guaranteed deterministic fallback
- GeneratedOutreachContent: Schema for generated personalization assets
- build_whatsapp_link: Formatter for wa.me click-to-chat links
- assert_zero_placeholders: Strict assertion utility against unparsed {{placeholders}}
- stage_draft_to_sheet, stage_drafts_to_sheet: Google Sheets staging helpers
"""

from src.personalizer.generator import (
    PersonalizerGenerator,
    build_whatsapp_link,
    extract_lead_context,
    stage_draft_to_sheet,
    stage_drafts_to_sheet,
)
from src.personalizer.llm_engine import (
    GeneratedOutreachContent,
    LLMEngine,
    extract_json_payload,
    validate_icebreaker_invariants,
)
from src.personalizer.prompts import (
    EMAIL_BODY_TEMPLATES,
    EMAIL_SUBJECT_TEMPLATES,
    ICEBREAKER_TEMPLATES,
    OFFER_ANGLE_TEMPLATES,
    SYSTEM_PROMPT_PERSONALIZER,
    WHATSAPP_TEMPLATES,
)
from src.personalizer.template_engine import (
    TemplateEngine,
    assert_zero_placeholders,
    sanitize_company_name,
)

__all__ = [
    "PersonalizerGenerator",
    "TemplateEngine",
    "LLMEngine",
    "GeneratedOutreachContent",
    "build_whatsapp_link",
    "extract_lead_context",
    "stage_draft_to_sheet",
    "stage_drafts_to_sheet",
    "assert_zero_placeholders",
    "sanitize_company_name",
    "validate_icebreaker_invariants",
    "SYSTEM_PROMPT_PERSONALIZER",
    "ICEBREAKER_TEMPLATES",
    "OFFER_ANGLE_TEMPLATES",
    "EMAIL_SUBJECT_TEMPLATES",
    "EMAIL_BODY_TEMPLATES",
    "WHATSAPP_TEMPLATES",
]
