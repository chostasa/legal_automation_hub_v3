import os
import html
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
    if not text:
        return ""
    prompt = f"""
{FULL_SAFETY_PROMPT}

Polish the following mediation memo section:
- Remove redundancy and filler
- Keep each paragraph focused and persuasive
- Standardize titles (Mr./Ms.), citations, and punctuation
- Use active voice only

Section:
{text}
"""
    return safe_generate(prompt=prompt, model="gpt-4-turbo")

def final_polish_memo(memo_data: dict) -> dict:
    joined = "\n\n".join([f"## {k}\n{v}" for k, v in memo_data.items()])
    prompt = f"""{FULL_SAFETY_PROMPT}
{FULL_SAFETY_PROMPT}

Perform a final polish on this full mediation memo:
1. Remove any duplicated facts between Parties, Facts/Liability, and Conclusion.
2. Ensure smooth transitions between sections with light connective phrasing.
3. Standardize all names, titles, and citations.
4. Keep each section concise and ensure it serves a unique purpose.

Full Memo:
{joined}
"""
    cleaned = safe_generate(prompt=prompt, model="gpt-4-turbo")
    # Split back into sections by markers
    new_data = {}
    for section in memo_data.keys():
        if f"## {section}" in cleaned:
            new_data[section] = cleaned.split(f"## {section}")[1].split("##")[0].strip()
        else:
            new_data[section] = memo_data[section]
    return new_data

# === Quote Extraction ===
def generate_quotes_from_raw_depo(raw_text: str, categories: list) -> dict:
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
    if not quotes.strip():
        return ""
    prompt = f"""
{FULL_SAFETY_PROMPT}

We have the following deposition and complaint quotes:

{quotes}

Select up to 3 quotes that are most relevant for the **{section_name}** section. 
Only return the exact quotes (no paraphrasing). 

Context:
{context}
"""
    curated = safe_generate(prompt=prompt, model="gpt-4-turbo")
    return curated.strip()

# === Main Memo Generation ===
def generate_memo_from_fields(data: dict, template_path: str, output_dir: str) -> tuple:
    try:
        memo_data = {}
        plaintiffs = data.get("plaintiffs", "")
        defendants = data.get("defendants", "")

        # Deduplicate and select unique quotes for liability and damages
        liability_quotes = curate_quotes_for_section(
            "Facts & Liability", 
            data.get("liability_quotes", ""), 
            data.get('complaint_narrative', '')
        )
        damages_quotes = curate_quotes_for_section(
            "Harms & Losses", 
            data.get("damages_quotes", ""), 
            data.get('medical_summary', '')
        )

        # === Introduction ===
        intro_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft a concise Introduction section. Do not repeat facts.
Use this input:
- Complaint Narrative: {data.get('complaint_narrative', '')}
- Party Information: {data.get('party_information_from_complaint', '')}

Example:
{INTRO_EXAMPLE}
"""
        memo_data["Introduction"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(intro_prompt, 3000),
            model="gpt-4-turbo",
            system_msg=INTRO_MSG
        )))

        # === Parties Section ===
        parties_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Parties section:
- Identify each Plaintiff and Defendant and their role
- Do NOT repeat facts about the accident or injuries (keep this purely role-based)
- Limit to 1-2 sentences per party

Party Information:
{data.get('party_information_from_complaint', '')}

Example:
{PLAINTIFF_STATEMENT_EXAMPLE}
"""
        memo_data["Parties"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(parties_prompt, 3000),
            model="gpt-4-turbo",
            system_msg=PARTIES_MSG
        )))

        # === Individual Plaintiff Narratives ===
        for i in range(1, 4):
            name = data.get(f"plaintiff{i}", "").strip()
            if name:
                plaintiff_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft a narrative paragraph for Plaintiff {name}.
Use only party information, do NOT restate accident facts or damages.

Party Information:
{data.get('party_information_from_complaint', '')}

Example:
{PLAINTIFF_STATEMENT_EXAMPLE}
"""
                memo_data[f"Plaintiff_{i}"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
                    prompt=trim_to_token_limit(plaintiff_prompt, 2500),
                    model="gpt-4-turbo",
                    system_msg=PLAINTIFF_MSG
                )))
            else:
                memo_data[f"Plaintiff_{i}"] = ""

        # === Individual Defendant Narratives ===
        for i in range(1, 8):
            name = data.get(f"defendant{i}", "").strip()
            if name:
                all_party_info = data.get('party_information_from_complaint', '')
                defendant_info = "\n".join([
                    line for line in all_party_info.splitlines() if name.lower() in line.lower()
                ]) or all_party_info
                defendant_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft a narrative paragraph for Defendant {name}.
Use only this defendant's information, avoid restating accident facts.

Defendant Info:
{defendant_info}

Example:
{DEFENDANT_STATEMENT_EXAMPLE}
"""
                memo_data[f"Defendant_{i}"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
                    prompt=trim_to_token_limit(defendant_prompt, 2500),
                    model="gpt-4-turbo",
                    system_msg=DEFENDANT_MSG
                )))
            else:
                memo_data[f"Defendant_{i}"] = ""

        # === Facts & Liability ===
        facts_prompt = f"""
{FULL_SAFETY_PROMPT}

Write the Facts & Liability section:
- Establish duty, breach, and causation
- Embed at least 3 unique liability quotes with proper citations
- Do NOT reintroduce party roles or injuries (covered elsewhere)

Complaint Narrative:
{data.get('complaint_narrative', '')}

Liability Quotes:
{liability_quotes}

Example:
{FACTS_LIABILITY_EXAMPLE}
"""
        memo_data["Facts_Liability"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(facts_prompt, 3500),
            model="gpt-4-turbo",
            system_msg=FACTS_MSG
        )))

        # === Causation/Injuries ===
        causation_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Causation/Injuries section. Connect accident facts to injuries and treatments.

Medical Summary:
{data.get('medical_summary', '')}

Example:
{CAUSATION_EXAMPLE}
"""
        memo_data["Causation_Injuries_Treatment"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(causation_prompt, 3000),
            model="gpt-4-turbo",
            system_msg=CAUSATION_MSG
        )))

        # === Harms & Losses ===
        harms_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Harms & Losses section:
- Show functional, professional, and emotional impact
- Embed at least 3 unique damages quotes inline

Medical Summary:
{data.get('medical_summary', '')}

Damages Quotes:
{damages_quotes}

Example:
{HARMS_EXAMPLE}
"""
        memo_data["Additional_Harms_Losses"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(harms_prompt, 3000),
            model="gpt-4-turbo",
            system_msg=HARMS_MSG
        )))

        # === Future Medical Bills ===
        future_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Future Medical Bills section:
- Outline anticipated care and costs
- Reference supporting testimony or records

Future Care Summary:
{data.get('future_medical_bills', '')}

Example:
{FUTURE_BILLS_EXAMPLE}
"""
        memo_data["Future_Medical_Bills"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(future_prompt, 2500),
            model="gpt-4-turbo",
            system_msg=FUTURE_MSG
        )))

        # === Conclusion ===
        conclusion_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Conclusion:
- Summarize settlement posture in 1-2 sentences
- End firmly with litigation readiness language

Settlement Summary:
{data.get('settlement_summary', '')}

Example:
{CONCLUSION_EXAMPLE}
"""
        memo_data["Conclusion"] = polish_text_for_legal_memo(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(conclusion_prompt, 2500),
            model="gpt-4-turbo",
            system_msg=CONCLUSION_MSG
        )))

        # === Final Cross-Section Polish ===
        memo_data = {k: html.unescape(v) for k, v in memo_data.items()}
        final_text = final_polish_memo(memo_data)

        # === Static Template Fields ===
        memo_data.update({
            "Court": html.unescape(data.get("court", "")),
            "Case_Number": html.unescape(data.get("case_number", "")),
            "Plaintiffs": html.unescape(plaintiffs),
            "Defendants": html.unescape(defendants),
            "Demand": html.unescape(data.get("settlement_summary", ""))
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
    try:
        sections = [
            "Introduction", "Parties", "Facts_Liability",
            "Causation_Injuries_Treatment", "Additional_Harms_Losses",
            "Future_Medical_Bills", "Conclusion"
        ]
        return "\n\n".join([
            f"## {s.replace('_', ' ')}\n\n{html.unescape(data.get(s, '').strip())}" for s in sections
        ])
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to generate plaintext memo: {e}"))
        return ""
