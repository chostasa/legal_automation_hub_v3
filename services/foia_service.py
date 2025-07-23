import os
from services.openai_client import safe_generate
from utils.docx_utils import replace_text_in_docx_all
from utils.token_utils import trim_to_token_limit
from utils.thread_utils import run_in_thread
from core.security import sanitize_text, redact_log
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

# === PROMPT BUILDING (with hardcoded example set) ===
def build_request_prompt(data: dict) -> str:
    return f"""
You are drafting FOIA bullet points for a civil legal claim.

Case synopsis:
{data['synopsis']}

Case type: {data['case_type']}
Facility or system involved: {data['facility_or_system']}
Defendant role: {data['recipient_role']}

Explicit instructions:
{data.get('explicit_instructions') or "None provided"}

Common requests or priorities:
{data.get('potential_requests') or "None provided"}

Please return a detailed and **role-specific** list of records, documents, media, and internal communications that a skilled civil attorney would request from this type of facility or entity. 
Only include items that would reasonably be within the possession, custody, or control of a {data['recipient_role']} operating within a {data['facility_or_system']}. Do not include irrelevant medical, financial, or third-party institutional records if they would not be held by this entity.

Format output as Word-style bullet points using asterisks (*).

=== EXAMPLES ===
• Any and all incident reports, including initial responder documentation, internal agency reports, and witness statements regarding the event;
• Any and all photographs, videos, surveillance footage, or imaging depicting the incident or the individuals or vehicles involved before, during, or after the event;
• Any and all correspondence, emails, call logs, complaints, or other documents discussing safety hazards, complaints, or warnings related to the area or subject of the incident;
• Any and all inspection records or maintenance logs for the area or equipment involved in the incident, including reports of deficiencies and records of repairs or upgrades;
• Any and all safety audits, risk assessments, compliance evaluations, or recommendations for safety improvements made by internal or external entities;
• Any and all prior complaints, reports of similar incidents, near-misses, or operational concerns relevant to the location or system involved in the incident;
• Any and all internal communications, memoranda, or correspondence related to the incident or any prior concerns about the safety or condition of the area or system involved;
• Any and all operational records for the system or facility in question, including logs, schedules, and deviations from normal operations around the time of the incident;
• Any and all surveillance or monitoring system footage, including any available black box, body camera, dashcam, or building camera recordings relevant to the event;
• Any and all historical records of similar accidents, injuries, or safety complaints in the same area or facility, spanning the past several decades;
• Any and all maintenance logs, service records, or repair histories related to the location, equipment, or personnel involved in the incident;
• Any and all evaluations, studies, or engineering assessments related to safety conditions, risks, or recommended upgrades in the area where the incident occurred;
• Any and all documentation of previous incidents or accidents in the relevant area, including safety complaints and related agency responses;
• Any and all internal records or communications reflecting the agency’s involvement in the investigation or response to the incident;
• Any and all agendas, meeting minutes, or discussion records referencing the incident or safety concerns prior to the incident;
• Any and all documentation related to historical safety efforts, maintenance schedules, and inspection results relevant to the location or parties involved;
• Any and all records of proposed or completed construction, maintenance, or upgrades that relate to the facility or location of the incident;
• Any and all inter-agency or third-party communications concerning safety risks, required improvements, or regulatory concerns in the location or facility involved;
• Any and all records discussing legal, operational, or jurisdictional responsibility for the facility, area, or process related to the incident;
• Any and all reports or documentation prepared in relation to the incident;
• Any and all supporting documentation, exhibits, summaries, or analysis prepared during or following the investigation into the incident;
• Any and all reports detailing emergency responses to incidents involving minors or vulnerable individuals at the facility;
• Any and all incident reports generated in response to calls concerning misconduct, abuse, or harm involving facility staff or agents;
• Any and all transcripts or audio recordings of emergency calls (e.g., 911) made in connection with the incident or similar events;
• Any and all written or recorded communications by emergency responders referencing the incident or the individuals involved;
• Any and all statements, testimony, or interviews with emergency responders related to the incident;
• Any and all investigative reports or files related to incidents involving harm to minors, patients, or clients in the facility's custody or care.

Only return the list.

Do not include placeholder terms like “[Client Name]”, “[date]”, “[location]”, or similar.
Refer to “the incident” or “the snowplow incident” as needed.
Do not fabricate or assume facts not provided.

Each bullet point must appear on its own line using asterisks (*).
Do not combine multiple bullets into one paragraph.

{DEFAULT_SAFETY}
""".strip()

def build_letter_prompt(data: dict, request_list: str, example_text: str = "") -> str:
    style_snippet = f"""
Match the tone, structure, and legal phrasing of the following example letter:

{trim_to_token_limit(example_text, 1200)}
""" if example_text else ""

    return f"""
You are a legal assistant generating a formal FOIA request letter on behalf of a civil law firm.

Client ID: {data['client_id']}
Recipient Agency: {data['recipient_name']}
Date of Incident: {data['doi']}
Location of Incident: {data['location']}
Case Type: {data['case_type']}
Facility/System: {data['facility_or_system']}
Recipient Role: {data['recipient_role']}

Case Summary:
{data['synopsis']}

Records Requested:
{request_list}

{style_snippet}

Write a clear, formal FOIA request letter that:
- References the incident and the client’s injuries or harm
- Includes the requested records (summarized or embedded)
- Uses active voice and professional tone
- Closes with a formal response deadline and contact info

Avoid filler like “I can assist with…” or “Please provide…” and do not refer to yourself.

{DEFAULT_SAFETY}
""".strip()

# === SYNOPSIS GENERATOR ===
def generate_synopsis(case_synopsis: str) -> str:
    prompt = f"""
Summarize the following legal case background in 2 professional sentences explaining what happened and the resulting harm or damages. Do not include any parties' names or personal identifiers:

{case_synopsis}
"""
    return run_in_thread(safe_generate, "You are a legal summarization assistant.", prompt)

# === MAIN GENERATOR ===
def generate_foia_request(data: dict, template_path: str, output_path: str, example_text: str = "") -> tuple:
    try:
        # 🔐 Sanitize all input fields
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = sanitize_text(v)

        # ✂️ Generate synopsis and request bullets
        data["synopsis"] = run_in_thread(
            safe_generate,
            prompt=f"""
        Summarize the following legal case background in 2 professional sentences explaining what happened and the resulting harm or damages. Do not include any parties' names or personal identifiers:

        {data.get("synopsis", "")}
        """
        )

        bullet_prompt = build_request_prompt(data)
        request_list = run_in_thread(safe_generate, prompt=bullet_prompt)

        # 🧠 Generate FOIA body letter
        letter_prompt = build_letter_prompt(data, request_list, example_text)
        foia_body = run_in_thread(safe_generate, prompt=letter_prompt)
        foia_body = sanitize_text(foia_body)

        # 🧩 Replace into DOCX template
        replacements = {
            "date": data.get("formatted_date", ""),
            "client_id": data.get("client_id", ""),
            "defendant_name": data.get("recipient_name", ""),
            "defendant_line1": data.get("recipient_line1", ""),
            "defendant_line2": data.get("recipient_line2", ""),
            "location": data.get("location", ""),
            "doi": data.get("doi", ""),
            "synopsis": data["synopsis"],
            "foia_request_bullet_points": [
                re.sub(r"^\*\s+", "", line).strip()
                for line in request_list.split("\n")
                if line.strip()
            ],
            "Body": foia_body,
        }

        run_in_thread(replace_text_in_docx_all, template_path, replacements, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("❌ FOIA DOCX file was not created.")

        return output_path, foia_body

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("FOIA request generation failed.")