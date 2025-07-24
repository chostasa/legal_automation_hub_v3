import os
import re
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
from core.prompts.foia_guidelines import FULL_SAFETY_PROMPT
from core.prompts.foia_example import FOIA_BULLET_POINTS_EXAMPLES

DEFAULT_SAFETY = "\n\n".join([
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    BAN_PHRASES_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
])

# === PROMPT BUILDING ===
def build_request_prompt(data: dict) -> str:
    return f"""
You are drafting FOIA bullet points for a civil legal claim.

Case synopsis:
{data['synopsis']}

Case type: {data['case_type']}
Facility or system involved: {data['facility_system']}
Defendant role: {data['recipient_role']}

Explicit instructions:
{data.get('explicit_instructions') or "None provided"}

Common requests or priorities:
{data.get('potential_requests') or "None provided"}

Please return a detailed and **role-specific** list of records, documents, media, and internal communications that a skilled civil attorney would request from this type of facility or entity. 
Only include items that would reasonably be within the possession, custody, or control of a {data['recipient_role']} operating within a {data['facility_system']}. Do not include irrelevant medical, financial, or third-party institutional records if they would not be held by this entity.

Format output as Word-style bullet points using asterisks (*).

=== EXAMPLES ===
{FOIA_BULLET_POINTS_EXAMPLES}

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
Facility/System: {data['facility_system']}
Recipient Role: {data['recipient_role']}

Case Summary:
{data['synopsis_summary']}

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
def generate_synopsis(casesynopsis: str) -> str:
    prompt = f"""
Summarize the following legal case background in 2 professional sentences explaining what happened and the resulting harm or damages. Do not include any parties' names or personal identifiers:

{casesynopsis}

{FULL_SAFETY_PROMPT}
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
        raw_synopsis = data.get("synopsis", "").strip()
        if raw_synopsis:
            data["synopsis_summary"] = generate_synopsis(raw_synopsis)
        else:
            data["synopsis_summary"] = "[No synopsis provided]"

        bullet_prompt = build_request_prompt(data)
        request_list = run_in_thread(safe_generate, prompt=bullet_prompt)

        # 🧠 Generate FOIA body letter
        letter_prompt = build_letter_prompt(data, request_list, example_text)
        foia_body = run_in_thread(safe_generate, prompt=letter_prompt)
        foia_body = sanitize_text(foia_body)

        # 🧩 Replace into DOCX template
        replacements = {
            "date": data.get("formatted_date", ""),
            "clientid": data.get("client_id", ""),
            "defendantname": data.get("recipient_name", ""),
            "defendantline1": data.get("recipient_address_1", ""),
            "defendantline2": data.get("recipient_address_2", ""),
            "location": data.get("location", ""),
            "doi": data.get("doi", ""),
            "synopsis": data.get("synopsis_summary", ""),
            "statecitation": data.get("state_citation", ""),
            "stateresponsetime": data.get("state_response_time", ""),
        }

        # 🧼 Escape accidental template braces
        for k, v in replacements.items():
            if isinstance(v, str):
                replacements[k] = v.replace("{{", "{ {").replace("}}", "} }")

        # 🔎 DEBUG
        print("\n🔍 FOIA Template Replacements:")
        for k, v in replacements.items():
            print(f"  - {k}: {v[:100]!r}{'...' if len(v) > 100 else ''}")

        try:
            run_in_thread(replace_text_in_docx_all, template_path, replacements, output_path)
        except Exception as docx_error:
            logger.warning(f"⚠️ DOCX rendering error: {docx_error}")
            # Try writing a backup template with only the plain text FOIA body for inspection
            with open(output_path.replace(".docx", "_FAILED.txt"), "w", encoding="utf-8") as f:
                f.write("⚠️ Failed to render DOCX — inspect the following:\n\n")
                for k, v in replacements.items():
                    f.write(f"<<{k}>>: {v}\n\n")
            raise RuntimeError("⚠️ Template render failed — fallback .txt file created.")

        if not os.path.exists(output_path):
            raise RuntimeError("❌ FOIA DOCX file was not created.")

        return output_path, foia_body, request_list.splitlines()

    except Exception as e:
        logger.error(redact_log(f"❌ FOIA generation failed: {e}"))
        raise RuntimeError("FOIA request generation failed.")
