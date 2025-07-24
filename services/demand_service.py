import os
from datetime import datetime
from core.generators.demand import generate_demand_sections
from utils.docx_utils import replace_text_in_docx_all
from utils.thread_utils import run_in_thread
from core.security import sanitize_text
from logger import logger

def generate_demand_letter(
    client_name, defendant, location, incident_date,
    summary, damages, template_path, output_path
):
    try:
        # === First Name Extraction ===
        first_name = client_name.strip().split()[0]

        # === Generate Sections via GPT abstraction
        sections = generate_demand_sections(client_name, first_name, summary, damages)

        # === Format & Replace in Word Template
        run_in_thread(
            replace_text_in_docx_all,
            template_path,
            {
                "Client Name": client_name,
                "Defendant": defendant,
                "Location": location,
                "IncidentDate": incident_date,
                "Brief Synopsis": sanitize_text(sections["brief_synopsis"]),
                "Demand": sanitize_text(sections["demand"]),
                "Damages": sanitize_text(sections["damages"]),
                "Settlement Demand": sanitize_text(sections["settlement"]),
            },
            output_path
        )

        return output_path, sections["brief_synopsis"]

    except Exception as e:
        logger.error(f"❌ Failed to generate demand letter: {e}")
        raise RuntimeError(f"Demand letter generation failed: {e}")
