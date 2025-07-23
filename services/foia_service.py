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
• Any and all highway-rail grade crossing incident reports, including initial accident reports, police or first responder reports submitted to the FRA, internal FRA documentation concerning the accident, and any witness statements or interviews conducted as part of the investigation;
• Any and all photographs, videos, surveillance footage, or imaging depicting the March 18, 2024 incident, or the truck or train involved in the collision immediately prior to, during, or immediately following the incident;
• Any and all correspondence, filings, emails, call logs, call recordings, complaints or other documents regarding the safety of or hazards imposed by the railroad crossing from 1990 to present;
• Any and all track inspection history for the segment of track at or near the railroad crossing, including routine and special inspection reports, records of deficiencies found during inspections, correspondence regarding any required or recommended repairs, and work orders or maintenance logs indicating repairs, modifications, or upgrades;
• Any and all safety audits of the crossing, including risk assessments conducted by the FRA; evaluations of crossing visibility, signaling, and warning devices; reports analyzing compliance with federal, state, or local safety regulations; and recommendations for safety improvements made by the FRA;
• Any and all complaints and prior accident reports associated with the railroad crossing, including complaints from the public, local government agencies, or railroad employees regarding the crossing's safety; reports of previous train-vehicle or train-pedestrian collisions at the location; and documentation of near-miss incidents or operational concerns;
• Any and all communication records related to the safety of the crossing before and after the March 18, 2024, accident, including emails, letters, or internal memoranda, as well as correspondence between the FRA and BNSF Railway, ODOT, or local authorities regarding maintenance, safety measures, or proposed improvements;
• Any and all data on train operations at the crossing, including records of train speeds and scheduled operations through the crossing, as well as any reports of delays or deviations from normal operations near the crossing on or around March 18, 2024;
• Any and all video footage or surveillance records, including any available locomotive event recorder (black box) data related to the accident and footage from onboard train cameras or nearby traffic cameras; and
• Any and all records, reports, correspondence, or other documentation concerning other motor vehicle accidents or injuries at the railroad crossing from 1990 to present.
Any and all maintenance logs for the railroad crossing, including records of inspections, repairs, modifications, or other maintenance activities conducted by or reported to ODOT;
• Any and all recommendations or evaluations relating to the railroad crossing, including internal assessments, third-party evaluations, proposed safety improvements, and engineering studies regarding the crossing’s condition or necessary upgrades;
• Any and all complaints or records of prior accidents at the railroad crossing, including reports submitted by the public, local government agencies, railroad personnel, or other stakeholders regarding safety concerns, near-misses, or previous collisions;
• Any and all records of ODOT’s involvement in response to this incident, including internal communications, coordination with law enforcement or emergency responders, and any actions taken following the March 18, 2024, accident;
• Any and all meeting minutes or records of discussions related to the safety of the railroad crossing, including agendas, notes, or transcripts from meetings involving ODOT, local officials, railroad representatives, or other relevant stakeholders;
• Any and all documents, reports, correspondence, or records concerning the inspection, maintenance, or safety improvements of the railroad crossing from 1990 to the present. This would encompass historical safety efforts, recommendations, and maintenance schedules;
• Records regarding any construction, maintenance, or safety improvements planned or implemented at the railroad crossing from 1990 to the present, including any planned upgrades or pending projects at the site to improve safety or functionality;
• Any and all records related to the communication between ODOT and third parties (including but not limited to BNSF Railway Company, local municipalities, or other agencies) concerning the safety, condition, or need for repair, maintenance, or other improvements to the railroad crossing; and
• Any and all documents or records concerning the jurisdictional responsibility of ODOT for maintaining the railroad crossing and any cross-agency discussions regarding safety protocols or enforcement of regulations at the crossing.
• Any and all reports related to this occurrence, (Case Number: 2024-0856);
• Any and all additional documents prepared in relation to this incident.
• Any and all NRFD reports documenting responses to incidents involving agents and/or employees of Hartgrove Hospital concerning a patient and/or minor during the time period from 1984 to the present.
• Any and all incident reports generated by the NRFD detailing responses to calls involving agents and/or employees of Hartgrove Hospital concerning a student and/or minor during the time period from 1984 to the present.
• Any and all recordings and/or transcripts of emergency calls (e.g., 911 calls) made to the NRFD or emergency services related to incidents involving agents and/or employees of Hartgrove Hospital concerning a patient and/or minor during the time period from 1984 to the present.
• Any and all communications, whether written or recorded, received by or sent from the NRFD, referencing incidents involving agents and/or employees of Hartgrove Hospital concerning a patient and/or minor during the time period from 1984 to the present.
• Copies of any and all statements, whether written or recorded, involving NRFD personnel or emergency responders in relation to investigations into incidents involving agents and/or employees of Hartgrove Hospital
Any and all BFS reports documenting responses to incidents involving agents and/or employees of Streamwood Hospital concerning a patient and/or minor during the time period from 1983 to the present.
• Any and all incident reports generated by the BFS detailing responses to calls involving agents and/or employees of Streamwood Hospital concerning a student and/or minor during the time period from 1983 to the present.
• Any and all recordings and/or transcripts of emergency calls (e.g., 911 calls) made to the BFS or emergency services related to incidents involving agents and/or employees of Streamwood Hospital concerning a patient and/or minor during the time period from 1983 to the present.
• Any and all communications, whether written or recorded, received by or sent from the BFS, referencing incidents involving agents and/or employees of Streamwood Hospital concerning a patient and/or minor during the time period from 1983 to the present.
• Copies of any and all statements, whether written or recorded, involving BFS personnel or emergency responders in relation to investigations into incidents involving agents and/or employees of Streamwood Hospital concerning a student and/or minor during the time period from 1983 to the present.
• Complete copies of any and all BFS investigative reports and/or files related to incidents involving a minor/student and agents and/or employees of Streamwood Hospital during the time period from 1983 to the present.
Only return the list.

Do not use placeholders like “[date]” or “[location]”. You may refer generally to “the incident” or “the snowplow incident” if needed.

Ensure that each bullet point is on its own line. Do not cluster or compress the items into a single paragraph.

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
            "foia_request_bullet_points": "\n".join(request_list.split("\n")),,
            "Body": foia_body
        }

        run_in_thread(replace_text_in_docx_all, template_path, replacements, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("❌ FOIA DOCX file was not created.")

        return output_path, foia_body

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("FOIA request generation failed.")
