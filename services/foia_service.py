import os
from core.openai_client import safe_generate
from utils.docx_utils import replace_text_in_docx_all
from core.token_utils import trim_to_token_limit
from core.security import sanitize_text
from utils.thread_utils import run_in_thread
from logger import logger


def generate_foia_request(client_name, agency_name, details, template_path, output_path):
    """
    Generates a FOIA request letter using GPT and fills the template.
    All blocking calls are offloaded to background threads for performance.
    """
    try:
        # ✅ Trim content for token safety
        facts = trim_to_token_limit(details, 2000)

        # 🧠 GPT Prompt
        prompt = f"""
Draft a FOIA request to {agency_name} regarding the following details for {client_name}:

{facts}
""".strip()

        # 🧵 Run GPT in background thread
        result = run_in_thread(safe_generate, "You are a government records request expert.", prompt)
        result = sanitize_text(result)

        # 🧵 Replace placeholders using threaded I/O
        run_in_thread(
            replace_text_in_docx_all,
            template_path,
            {
                "ClientName": client_name,
                "Agency": agency_name,
                "Details": details,
                "Body": result
            },
            output_path
        )

        return output_path, result

    except Exception as e:
        logger.error(f"❌ Failed to generate FOIA letter: {e}")
        raise RuntimeError(f"FOIA request generation failed: {e}")
