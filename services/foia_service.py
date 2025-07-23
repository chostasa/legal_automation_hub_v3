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

# 🔐 Default safety reinforcement for all GPT prompts
DEFAULT_SAFETY = "\n\n".join([
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    BAN_PHRASES_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
])

def build_request_prompt(data: dict) -> str:
    return f"""
You are drafting FOIA bullet points for a civil legal claim.

Case Synopsis:
{data['synopsis']}

Case Type: {data['case_type']}
Facility or System: {data['facility_or_system']}
Defendant Role: {data['recipient_role']}

Explicit Instructions:
{data['explicit_instructions'] or "None provided"}

Common Requests or Priorities:
{data['potential_requests']}

Please return a detailed and role-specific list of records, documents, media, and internal communications that a skilled civil attorney would request from this type of facility or entity. 
Only include items that would reasonably be within the possession, custody, or control of a {data['recipient_role']} operating within a {data['facility_or_system']}.

Format output as Word-style bullet points using asterisks (*). Only return the list.

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

{DEFAULT_SAFETY}
""".strip()

def generate_synopsis(case_summary: str) -> str:
    prompt = f"""
Summarize the following case background in 2 professional sentences explaining what occurred and the resulting harm. Do not include names or identifiers:

{case_summary}
"""
    return run_in_thread(safe_generate, "You are a legal summarization assistant.", prompt)

def generate_foia_request(data: dict, template_path: str, output_path: str, example_text: str = "") -> tuple:
    try:
        # 🔐 Sanitize all input fields
        for k, v in data.items():
            if isinstance(v, str):
                data[k] = sanitize_text(v)

        # ✂️ Generate synopsis and request bullets
        data["synopsis"] = generate_synopsis(data.get("synopsis", ""))
        bullet_prompt = build_request_prompt(data)
        request_list = run_in_thread(safe_generate, "You are a FOIA request generator.", bullet_prompt)
        request_list = sanitize_text(request_list).replace("* ", "• ")

        # 🧠 Full FOIA body letter with optional style
        letter_prompt = build_letter_prompt(data, request_list, example_text)
        foia_body = run_in_thread(safe_generate, "You are a legal letter writer.", letter_prompt)
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
            "foia_request_bullet_points": request_list,
            "Body": foia_body
        }

        run_in_thread(replace_text_in_docx_all, template_path, replacements, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("❌ FOIA DOCX file was not created.")

        return output_path, foia_body

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("FOIA request generation failed.")
