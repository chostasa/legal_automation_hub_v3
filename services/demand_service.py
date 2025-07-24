import os
from datetime import datetime
from core.generators.demand import generate_demand_sections
from utils.thread_utils import run_in_thread
from utils.docx_utils import replace_text_in_docx_all  # Uses raw find/replace, not Jinja
from core.security import sanitize_text
from logger import logger

def generate_demand_letter(
    client_name, defendant, location, incident_date,
    summary, damages, template_path, output_path,
    example_text=None
):
    try:
        # === First Name Extraction ===
        first_name = client_name.strip().split()[0]

        # === Generate Sections via GPT abstraction
        sections = generate_demand_sections(
            full_name=client_name,
            first_name=first_name,
            summary=summary,
            damages=damages,
            example_text=example_text
        )

        # === Manual Replace in Word Template (V2-style)
        replacements = {
            "{{ClientName}}": client_name,
            "{{Defendant}}": defendant,
            "{{Location}}": location,
            "{{IncidentDate}}": incident_date,
            "{{BriefSynopsis}}": sanitize_text(sections["brief_synopsis"]),
            "{{Demand}}": sanitize_text(sections["demand"]),
            "{{Damages}}": sanitize_text(sections["damages"]),
            "{{SettlementDemand}}": sanitize_text(sections["settlement"]),
        }

        run_in_thread(replace_text_in_docx_all, template_path, replacements, output_path)

        return output_path, sections["brief_synopsis"]

    except Exception as e:
        logger.error(f"❌ Failed to generate demand letter: {e}")
        raise RuntimeError(f"Demand letter generation failed: {e}")
