import os
from core.security import sanitize_text, redact_log
from utils.docx_utils import replace_text_in_docx_all
from services.openai_client import safe_generate
from utils.token_utils import trim_to_token_limit
from utils.template_engine import render_template_string
from core.generators.quote_parser import (
    normalize_deposition_lines,
    merge_multiline_qas,
    generate_quotes_in_chunks
)
from utils.thread_utils import run_in_thread
from logger import logger

# === Prompt Messages ===
INTRO_MSG = "You are a legal writer."
FACTS_MSG = "Summarize the facts and liability issues."
CAUSATION_MSG = "Summarize injuries and causation clearly."
HARMS_MSG = "Summarize damages and human harms."
CONCLUSION_MSG = "Draft a professional mediation conclusion."

# === Safety Notes (Appended to all GPT Prompts) ===
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


def generate_quotes_from_raw_depo(raw_text: str, categories: list) -> dict:
    try:
        lines = normalize_deposition_lines(raw_text)
        qa_text = merge_multiline_qas(lines)
        chunks = [qa_text[i:i + 9000] for i in range(0, len(qa_text), 9000)]
        return generate_quotes_in_chunks(chunks, categories=categories)
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to extract quotes from deposition: {e}"))
        return {}


def generate_memo_from_fields(data: dict, template_path, output_dir: str) -> tuple:
    """
    Accepts cleaned data dictionary and outputs filled-in memo.
    All blocking calls (GPT and file I/O) run in background threads.
    Returns (file_path, memo_data_dict)
    """
    try:
        content_sections = {}
        example_text = data.get("example_text", "").strip()
        example_clause = f"\n\nMatch the tone, structure, and style of this example:\n{example_text[:1500]}" if example_text else ""

        # === Section 1: Introduction
        intro_prompt = f"""
You are drafting the Introduction section of a mediation memo.
Plaintiffs: {data.get('plaintiffs')}.
Defendants: {data.get('defendants')}.
Court: {data.get('court')}. Case No: {data.get('case_number')}.
{example_clause}

{DEFAULT_SAFETY}
""".strip()

        content_sections["Introduction"] = run_in_thread(lambda: safe_generate(
            prompt=intro_prompt,
            model="gpt-3.5-turbo",
            system_msg=INTRO_MSG
        ))

        # === Section 2: Facts and Liability
        facts_prompt = f"""
Facts: {data['complaint_narrative']}
Liability Quotes: {data.get('liability_quotes', '')}
{example_clause}

{DEFAULT_SAFETY}
""".strip()

        content_sections["Facts_Liability"] = run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(facts_prompt, 3000),
            model="gpt-3.5-turbo",
            system_msg=FACTS_MSG
        ))

        # === Section 3: Causation / Medical
        medical_prompt = f"""
Settlement Summary: {data['settlement_summary']}
Medical Summary: {data['medical_summary']}
{example_clause}

{DEFAULT_SAFETY}
""".strip()

        content_sections["Causation_Injuries_Treatment"] = run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(medical_prompt, 3000),
            model="gpt-3.5-turbo",
            system_msg=CAUSATION_MSG
        ))

        # === Section 4: Damages / Harms
        damages_prompt = f"""
Damages narrative and harms to Plaintiff.
{data.get('damages_quotes', '')}
{example_clause}

{DEFAULT_SAFETY}
""".strip()

        content_sections["Additional_Harms_Losses"] = run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(damages_prompt, 2500),
            model="gpt-3.5-turbo",
            system_msg=HARMS_MSG
        ))

        # === Section 5: Conclusion
        conclusion_prompt = f"""
Plaintiffs are {data.get('plaintiffs')} and request confidential resolution.
{example_clause}

{DEFAULT_SAFETY}
""".strip()

        content_sections["Conclusion"] = run_in_thread(lambda: safe_generate(
            prompt=conclusion_prompt,
            model="gpt-3.5-turbo",
            system_msg=CONCLUSION_MSG
        ))

        # === Merge for Template Replacement
        memo_data = {
            "Court": data.get("court"),
            "Case_Number": data.get("case_number"),
            "Plaintiffs": data.get("plaintiffs"),
            "Defendants": data.get("defendants"),
            "Parties": data.get("party_information_from_complaint"),
            "Demand": data.get("settlement_summary"),
            "Future_Medical_Bills": data.get("future_medical_bills", ""),
            **content_sections
        }

        for i in range(1, 4):
            memo_data[f"Plaintiff_{i}"] = data.get(f"plaintiff{i}", "")
        for i in range(1, 8):
            memo_data[f"Defendant_{i}"] = data.get(f"defendant{i}", "")

        output_path = os.path.join(output_dir, "mediation_memo.docx")
        run_in_thread(replace_text_in_docx_all, template_path, memo_data, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("❌ Memo DOCX was not created.")

        return output_path, memo_data

    except Exception as e:
        logger.error(redact_log(f"❌ Memo generation failed: {e}"))
        raise RuntimeError("Memo generation failed.")


def generate_plaintext_memo(data: dict) -> str:
    """
    Creates a plaintext version of the memo based on the section outputs.
    """
    try:
        sections = [
            "Introduction",
            "Facts_Liability",
            "Causation_Injuries_Treatment",
            "Additional_Harms_Losses",
            "Conclusion"
        ]
        output = [f"## {section.replace('_', ' ')}\n\n{data.get(section, '').strip()}" for section in sections]
        return "\n\n".join(output)
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to generate plaintext memo: {e}"))
        return ""
