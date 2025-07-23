import os
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

def generate_foia_request(client_name: str, agency_name: str, details: str, template_path: str, output_path: str) -> tuple:
    """
    Generates a FOIA request letter using GPT and fills the Word template.
    All blocking steps are executed in background threads.
    Returns (output_path, generated_body).
    """
    try:
        # 🧼 Sanitize inputs
        client_name = sanitize_text(client_name)
        agency_name = sanitize_text(agency_name)
        details = sanitize_text(details)

        # ✂️ Trim for safety
        facts = trim_to_token_limit(details, 2000)

        # 🧠 GPT Prompt
        prompt = f"""
You are drafting a formal FOIA request to {agency_name} regarding the following incident involving {client_name}:

{facts}

{DEFAULT_SAFETY}
""".strip()

        # 🧵 Run GPT in background thread
        body = run_in_thread(
            safe_generate,
            "You are a government records request expert.",
            prompt
        )
        body = sanitize_text(body)

        # 🧵 Fill Word template using background thread
        run_in_thread(
            replace_text_in_docx_all,
            template_path,
            {
                "ClientName": client_name,
                "Agency": agency_name,
                "Details": details,
                "Body": body
            },
            output_path
        )

        if not os.path.exists(output_path):
            raise RuntimeError("❌ FOIA DOCX file was not created.")

        return output_path, body

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("FOIA request generation failed.")
