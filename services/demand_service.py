import os
from datetime import datetime
from docxtpl import DocxTemplate

from core.generators.demand import generate_demand_sections
from core.security import sanitize_text
from logger import logger

def generate_demand_letter(
    client_name, defendant, location, incident_date,
    summary, damages, template_path, output_path,
    example_text=None
):
    try:
        # === Extract first name for personalization ===
        first_name = client_name.strip().split()[0]

        # === Generate GPT-assisted demand sections ===
        sections = generate_demand_sections(
            full_name=client_name,
            first_name=first_name,
            summary=summary,
            damages=damages,
            example_text=example_text
        )

        # === Prepare Jinja2 context for docxtpl ===
        context = {
            "ClientName": client_name,
            "Defendant": defendant,
            "Location": location,
            "IncidentDate": incident_date,
            "BriefSynopsis": sanitize_text(sections["brief_synopsis"]),
            "Demand": sanitize_text(sections["demand"]),
            "Damages": sanitize_text(sections["damages"]),
            "SettlementDemand": sanitize_text(sections["settlement"]),
        }

        # === Load and render Word template ===
        doc = DocxTemplate(template_path)
        doc.render(context)
        doc.save(output_path)

        return output_path, sections["brief_synopsis"]

    except Exception as e:
        logger.error(f"❌ Failed to generate demand letter: {e}")
        raise RuntimeError(f"Demand letter generation failed: {e}")
