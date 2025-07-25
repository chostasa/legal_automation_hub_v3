import os
from core.security import sanitize_text, redact_log
from utils.docx_utils import replace_text_in_docx_all
from services.openai_client import safe_generate
from utils.token_utils import trim_to_token_limit
from utils.thread_utils import run_in_thread
from logger import logger

# === Import Guidelines & Examples ===
from core.prompts.memo_guidelines import FULL_SAFETY_PROMPT
from core.prompts.memo_examples import (
    INTRO_EXAMPLE,
    PLAINTIFF_STATEMENT_EXAMPLE,
    DEFENDANT_STATEMENT_EXAMPLE,
    DEMAND_EXAMPLE,
    FACTS_LIABILITY_EXAMPLE,
    CAUSATION_EXAMPLE,
    HARMS_EXAMPLE,
    FUTURE_BILLS_EXAMPLE,
    CONCLUSION_EXAMPLE
)
from core.generators.quote_parser import (
    normalize_deposition_lines,
    merge_multiline_qas,
    generate_quotes_in_chunks
)

# === System Messages ===
INTRO_MSG = "You are a senior legal writer drafting the Introduction."
FACTS_MSG = "You are a senior legal writer drafting the Facts & Liability section."
CAUSATION_MSG = "You are a senior legal writer drafting the Causation/Injuries section."
HARMS_MSG = "You are a senior legal writer drafting the Harms & Losses section."
FUTURE_MSG = "You are a senior legal writer drafting the Future Medical Expenses section."
CONCLUSION_MSG = "You are a senior legal writer drafting the Conclusion."
PARTIES_MSG = "You are a senior legal writer drafting the Parties section."
PLAINTIFF_MSG = "You are a senior legal writer drafting a plaintiff narrative paragraph."
DEFENDANT_MSG = "You are a senior legal writer drafting a defendant narrative paragraph."

# === Polishing Helpers ===
def polish_text_for_legal_memo(text: str) -> str:
    """Clean and polish each section for legal fluency."""
    if not text:
        return ""
    prompt = f"""
{FULL_SAFETY_PROMPT}

Polish the following mediation memo section:
- Eliminate redundancy and vague phrasing
- Strengthen transitions and section flow
- Maintain formal tone and active voice

Section:
{text}
"""
    return safe_generate(lambda p: p, prompt)

def polish_transitions(text: str) -> str:
    """Smooth paragraph-to-paragraph transitions."""
    if not text:
        return ""
    prompt = f"""
Smooth the flow and transitions between paragraphs without removing facts or quotes:

{text}
"""
    return safe_generate(lambda p: p, prompt)

# === Quote Extraction ===
def generate_quotes_from_raw_depo(raw_text: str, categories: list) -> dict:
    """Extract categorized quotes from deposition transcript."""
    try:
        lines = normalize_deposition_lines(raw_text)
        qa_text = merge_multiline_qas(lines)
        chunks = [qa_text[i:i + 9000] for i in range(0, len(qa_text), 9000)]
        return generate_quotes_in_chunks(chunks, categories=categories)
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to extract quotes from deposition: {e}"))
        return {}

# === Curate Quotes for Each Section ===
def curate_quotes_for_section(section_name: str, quotes: str, context: str) -> str:
    """Use GPT to select the most relevant quotes for a section."""
    if not quotes.strip():
        return ""

    prompt = f"""
{FULL_SAFETY_PROMPT}

We have the following quotes from depositions and complaints:

{quotes}

Select up to 3 quotes that are the most relevant for the **{section_name}** section 
of a mediation memo. Only return the exact quotes (do not rewrite).

Context:
{context}
"""
    curated = safe_generate(lambda p: p, prompt)
    return curated.strip()

# === Main Memo Generation ===
def generate_memo_from_fields(data: dict, template_path: str, output_dir: str) -> tuple:
    """Generate mediation memo sections and fill into DOCX template."""
    try:
        memo_data = {}
        plaintiffs = data.get("plaintiffs", "")
        defendants = data.get("defendants", "")

        # Deduplicate and select unique quotes for liability and damages
        used_quotes = set()
        def get_unique_quotes(quotes: str, count=3):
            selected = []
            for q in quotes.splitlines():
                q = q.strip()
                if q and q not in used_quotes:
                    selected.append(q)
                    used_quotes.add(q)
                if len(selected) == count:
                    break
            return "\n".join(selected)

        raw_liability_quotes = data.get("liability_quotes", "")
        liability_quotes = curate_quotes_for_section(
            "Facts & Liability", 
            raw_liability_quotes, 
            data.get('complaint_narrative', '')
        )

        raw_damages_quotes = data.get("damages_quotes", "")
        damages_quotes = curate_quotes_for_section(
            "Harms & Losses", 
            raw_damages_quotes, 
            data.get('medical_summary', '')
        )

        # === Introduction ===
        intro_prompt = f"""
{FULL_SAFETY_PROMPT}

Example:
{INTRO_EXAMPLE}

Draft the Introduction for a mediation memo:
- Plaintiffs: {plaintiffs}
- Defendants: {defendants}
- Court: {data.get('court')} (Case No: {data.get('case_number')})
"""
        memo_data["Introduction"] = polish_transitions(polish_text_for_legal_memo(
            run_in_thread(lambda: safe_generate(
                prompt=trim_to_token_limit(intro_prompt, 3000),
                model="gpt-3.5-turbo",
                system_msg=INTRO_MSG
            ))
        ))

        # === Parties Section ===
        parties_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Parties section summarizing all plaintiffs and defendants.
Plaintiffs: {plaintiffs}
Defendants: {defendants}
Party Info:
{data.get('party_information_from_complaint', '')}
"""
        memo_data["Parties"] = run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(parties_prompt, 3000),
            model="gpt-3.5-turbo",
            system_msg=PARTIES_MSG
        ))

        # === Individual Plaintiff Narratives ===
        for i in range(1, 4):
            name = data.get(f"plaintiff{i}", "").strip()
            if name:
                plaintiff_prompt = f"""
{FULL_SAFETY_PROMPT}

Example:
{PLAINTIFF_STATEMENT_EXAMPLE}

Write a complete narrative paragraph for Plaintiff {name}.
"""
                memo_data[f"Plaintiff_{i}"] = run_in_thread(lambda: safe_generate(
                    prompt=trim_to_token_limit(plaintiff_prompt, 2500),
                    model="gpt-3.5-turbo",
                    system_msg=PLAINTIFF_MSG
                ))
            else:
                memo_data[f"Plaintiff_{i}"] = ""

        # === Individual Defendant Narratives ===
        for i in range(1, 8):
            name = data.get(f"defendant{i}", "").strip()
            if name:
                defendant_prompt = f"""
{FULL_SAFETY_PROMPT}

Example:
{DEFENDANT_STATEMENT_EXAMPLE}

Write a complete narrative paragraph for Defendant {name}.
"""
                memo_data[f"Defendant_{i}"] = run_in_thread(lambda: safe_generate(
                    prompt=trim_to_token_limit(defendant_prompt, 2500),
                    model="gpt-3.5-turbo",
                    system_msg=DEFENDANT_MSG
                ))
            else:
                memo_data[f"Defendant_{i}"] = ""

        # === Facts & Liability ===
        facts_prompt = f"""
{FULL_SAFETY_PROMPT}

Embed at least 3 liability quotes inline.

Complaint Narrative:
{data.get('complaint_narrative', '')}

Liability Quotes:
{liability_quotes}

Example:
{FACTS_LIABILITY_EXAMPLE}
"""
        memo_data["Facts_Liability"] = polish_transitions(polish_text_for_legal_memo(
            run_in_thread(lambda: safe_generate(
                prompt=trim_to_token_limit(facts_prompt, 3500),
                model="gpt-3.5-turbo",
                system_msg=FACTS_MSG
            ))
        ))

        # === Causation/Injuries ===
        causation_prompt = f"""
{FULL_SAFETY_PROMPT}

Example:
{CAUSATION_EXAMPLE}

Medical Summary:
{data.get('medical_summary', '')}
"""
        memo_data["Causation_Injuries_Treatment"] = polish_text_for_legal_memo(
            run_in_thread(lambda: safe_generate(
                prompt=trim_to_token_limit(causation_prompt, 3000),
                model="gpt-3.5-turbo",
                system_msg=CAUSATION_MSG
            ))
        )

        # === Harms & Losses ===
        harms_prompt = f"""
{FULL_SAFETY_PROMPT}

Embed at least 3 damages quotes inline.

Damages Summary:
{data.get('medical_summary', '')}

Damages Quotes:
{damages_quotes}

Example:
{HARMS_EXAMPLE}
"""
        memo_data["Additional_Harms_Losses"] = polish_text_for_legal_memo(
            run_in_thread(lambda: safe_generate(
                prompt=trim_to_token_limit(harms_prompt, 3000),
                model="gpt-3.5-turbo",
                system_msg=HARMS_MSG
            ))
        )

        # === Future Medical Bills ===
        future_prompt = f"""
{FULL_SAFETY_PROMPT}

Example:
{FUTURE_BILLS_EXAMPLE}

Future Care:
{data.get('future_medical_bills', '')}
"""
        memo_data["Future_Medical_Bills"] = polish_text_for_legal_memo(
            run_in_thread(lambda: safe_generate(
                prompt=trim_to_token_limit(future_prompt, 2500),
                model="gpt-3.5-turbo",
                system_msg=FUTURE_MSG
            ))
        )

        # === Conclusion ===
        conclusion_prompt = f"""
{FULL_SAFETY_PROMPT}

Example:
{CONCLUSION_EXAMPLE}

Settlement Summary:
{data.get('settlement_summary', '')}
"""
        memo_data["Conclusion"] = polish_transitions(polish_text_for_legal_memo(
            run_in_thread(lambda: safe_generate(
                prompt=trim_to_token_limit(conclusion_prompt, 2500),
                model="gpt-3.5-turbo",
                system_msg=CONCLUSION_MSG
            ))
        ))

        # === Static Template Fields ===
        memo_data.update({
            "Court": data.get("court", ""),
            "Case_Number": data.get("case_number", ""),
            "Plaintiffs": plaintiffs,
            "Defendants": defendants,
            "Demand": data.get("settlement_summary", "")
        })

        # === Generate DOCX ===
        output_path = os.path.join(output_dir, f"Mediation_Memo_{plaintiffs or 'Unknown'}.docx")
        run_in_thread(replace_text_in_docx_all, template_path, memo_data, output_path)

        if not os.path.exists(output_path):
            raise RuntimeError("❌ Memo DOCX was not created.")

        return output_path, memo_data

    except Exception as e:
        logger.error(redact_log(f"❌ Memo generation failed: {e}"))
        raise RuntimeError("Memo generation failed.")

def generate_plaintext_memo(data: dict) -> str:
    """Return plaintext version of memo for quick preview."""
    try:
        sections = [
            "Introduction", "Parties", "Facts_Liability",
            "Causation_Injuries_Treatment", "Additional_Harms_Losses",
            "Future_Medical_Bills", "Conclusion"
        ]
        return "\n\n".join([
            f"## {s.replace('_', ' ')}\n\n{data.get(s, '').strip()}" for s in sections
        ])
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to generate plaintext memo: {e}"))
        return ""
