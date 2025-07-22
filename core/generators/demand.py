from services.openai_client import OpenAIClient
from prompts.prompt_factory import build_prompt
from core.security import redact_log
from logger import logger

openai = OpenAIClient()

def generate_demand_sections(full_name: str, first_name: str, summary: str, damages: str) -> dict:
    """
    Generate all GPT-based sections for the demand letter.
    Returns a sanitized replacements dict.
    """
    try:
        brief_synopsis_prompt = build_prompt("Brief Synopsis", summary, full_name)
        demand_prompt = build_prompt("Demand", summary, first_name)
        damages_prompt = build_prompt("Damages", damages, first_name)
        settlement_prompt = build_prompt("Settlement", f"{summary}\n\n{damages}", first_name)

        return {
            "brief_synopsis": openai.safe_generate(brief_synopsis_prompt),
            "demand": openai.safe_generate(demand_prompt),
            "damages": openai.safe_generate(damages_prompt),
            "settlement": openai.safe_generate(settlement_prompt),
        }

    except Exception as e:
        logger.error(redact_log(f"❌ GPT demand generation failed: {e}"))
        raise RuntimeError("Failed to generate GPT sections for demand letter.")
