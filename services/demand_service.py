import os
from datetime import datetime
from core.generators.demand import generate_demand_sections
from utils.docx_utils import replace_text_in_docx_all
from utils.thread_utils import run_in_thread
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

        # === Format & Replace in Word Template
        run_in_thread(
            replace_text_in_docx_all,
            template_path,
            {
                "Client_Name": client_name,
                "IncidentDate": incident_date,
                "Brief_Synopsis": sanitize_text(sections["brief_synopsis"]),
                "Demand": sanitize_text(sections["demand"]),
                "Damages": sanitize_text(sections["damages"]),
                "Settlement_Demand": sanitize_text(sections["settlement"]),
            },
            output_path
        )

        return output_path, sections["brief_synopsis"]

    except Exception as e:
        logger.error(f"❌ Failed to generate demand letter: {e}")
        raise RuntimeError(f"Demand letter generation failed: {e}")
