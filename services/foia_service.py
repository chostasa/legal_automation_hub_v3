import os
from services.openai_client import safe_generate
from utils.docx_utils import replace_text_in_docx_all
from utils.token_utils import trim_to_token_limit
from core.security import sanitize_text, redact_log
from utils.thread_utils import run_in_thread
from logger import logger

from core.banned_phrases import (
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    BAN_PHRASES_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
)

DEFAULT_SAFETY = "\n\n".join([
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    BAN_PHRASES_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
])


def generate_foia_request(data: dict, template_path: str, output_path: str) -> tuple:
    """
    Accepts a structured dict of FOIA input fields and generates a formal GPT-based FOIA letter.
    Returns (output_path, gpt_body_text).
    """
    try:
        # Sanitize and extract fields
        formatted_date = data.get("formatted_date", "")
        client_id = sanitize_text(data.get("client_id", ""))
        agency = sanitize_text(data.get("recipient_name", ""))
        defendant_line1 = sanitize_text(data.get("recipient_line1", ""))
        defendant_line2 = sanitize_text(data.get("recipient_line2", ""))
        location = sanitize_text(data.get("location", ""))
        doi = sanitize_text(data.get("doi", ""))
        synopsis = sanitize_text(data.get("synopsis", ""))
        request_bullets = sanitize_text(data.get("potential_requests", ""))
        instructions = sanitize_text(data.get("explicit_instructions", ""))
        case_type = sanitize_text(data.get("case_type", ""))
        system = sanitize_text(data.get("facility_or_system", ""))
        role = sanitize_text(data.get("recipient_role", ""))

        # Prompt to GPT
        prompt = f"""
You are drafting a professional FOIA request letter from a law firm.

Client: {client_id}
Agency: {agency}
Facility/System: {system}
Role: {role}
Date of Incident: {doi}
Location: {location}
Case Type: {case_type}

Case Summary:
{synopsis}

Requests:
{request_bullets}

Instructions:
{instructions}

Write a clear, formal FOIA request that:
- References the above incident and context
- Lists the types of information sought (bullet points are fine)
- Includes a closing paragraph with contact information
Avoid passive voice. Keep tone professional.

{DEFAULT_SAFETY}
""".strip()

        # Run GPT
        body = run_in_thread(safe_generate, "You are a legal records request writer.", prompt)
        body = sanitize_text(body)

        # Replace placeholders
        replacements = {
            "date": formatted_date,
            "defendant_name": agency,
            "defendant_line1": defendant_line1,
            "defendant_line2": defendant_line2,
            "client_id": client_id,
            "location": location,
            "doi": doi,
            "synopsis": synopsis,
            "foia_request_bullet_points": request_bullets,
            "Body": body
        }

        run_in_thread(replace_text_in_docx_all, template_path, replacements, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("❌ FOIA DOCX file was not created.")

        return output_path, body

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("FOIA request generation failed.")
