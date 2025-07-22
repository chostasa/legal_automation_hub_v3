import os
from core.openai_client import safe_generate
from utils.docx_utils import replace_text_in_docx_all
from core.security import sanitize_text
from utils.token_utils import trim_to_token_limit
from utils.thread_utils import run_in_thread
from logger import logger


def generate_demand_letter(client_name, defendant, summary, damages, template_path, output_path):
    """
    Generates a demand letter using GPT and fills the Word template.
    All blocking steps are executed in background threads.
    """
    try:
        facts = trim_to_token_limit(summary, 2000)
        demand_prompt = f"""
You are drafting a legal demand letter on behalf of {client_name} against {defendant}.
Facts: {facts}
Damages: {damages}
Write this in a formal legal tone.
""".strip()

        body = run_in_thread(safe_generate, "You are a legal writer.", demand_prompt)
        body = sanitize_text(body)

        run_in_thread(
            replace_text_in_docx_all,
            template_path,
            {
                "ClientName": client_name,
                "Defendant": defendant,
                "Summary": summary,
                "Damages": damages,
                "Body": body
            },
            output_path
        )

        return output_path, body

    except Exception as e:
        logger.error(f"❌ Failed to generate demand letter: {e}")
        raise RuntimeError(f"Demand letter generation failed: {e}")
