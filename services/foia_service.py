import os
from datetime import datetime
from services.openai_client import safe_generate
from utils.docx_utils import replace_text_in_docx_all
from utils.token_utils import trim_to_token_limit
from core.security import sanitize_text, redact_log
from utils.thread_utils import run_in_thread
from logger import logger

# === Safety Notes for All Prompts ===
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
    Generates a FOIA request letter using GPT and fills the Word template.
    Accepts sanitized data dict with full FOIA metadata.
    Returns (output_path, generated_body).
    """
    try:
        # ⏳ Prepare inputs
        formatted_date = datetime.today().strftime("%B %d, %Y")
        synopsis = trim_to_token_limit(data.get("case_synopsis", ""), 2000)
        explicit_instructions = data.get("explicit_instructions", "")

        # ✍️ Prompt with full context
        prompt = f"""
You are drafting a formal FOIA request letter for legal counsel.

Recipient: {data.get("recipient_name")}
Client ID: {data.get("client_id")}
Incident Date: {data.get("date_of_incident")}
Location: {data.get("location")}
Case Type: {data.get("case_type")}
Facility/System: {data.get("facility_system")}
Synopsis: {synopsis}

Potential Records Requests:
{data.get("potential_requests", "")}

Explicit Instructions (optional):
{explicit_instructions}

{DEFAULT_SAFETY}
""".strip()

        # 🧠 Generate letter body using GPT
        body = run_in_thread(
            safe_generate,
            "You are a government records request expert.",
            prompt
        )
        body = sanitize_text(body)

        # 📄 Prepare replacements for template
        replacements = {
            "date": formatted_date,
            "defendant_name": data.get("recipient_name", ""),
            "defendant_line1": data.get("recipient_address_1", ""),
            "defendant_line2": data.get("recipient_address_2", ""),
            "client_id": data.get("client_id", ""),
            "location": data.get("location", ""),
            "doi": data.get("date_of_incident", ""),
            "synopsis": synopsis,
            "foia_request_bullet_points": data.get("potential_requests", ""),
            "Body": body
        }

        run_in_thread(
            replace_text_in_docx_all,
            template_path,
            replacements,
            output_path
        )

        if not os.path.exists(output_path):
            raise RuntimeError("❌ FOIA DOCX file was not created.")

        return output_path, body

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("FOIA request generation failed.")
