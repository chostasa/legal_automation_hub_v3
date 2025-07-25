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
INTRO_MSG = "Draft a concise, persuasive Introduction."
PARTIES_MSG = "Summarize parties' roles without redundancy."
FACTS_MSG = "Draft a forceful Facts & Liability section."
CAUSATION_MSG = "Draft a clear Causation & Injuries section."
HARMS_MSG = "Draft a strong Harms & Losses section with embedded quotes."
FUTURE_MSG = "Draft the Future Medical Expenses section."
CONCLUSION_MSG = "Draft a strong Conclusion with a call to action."
PLAINTIFF_MSG = "Write a single plaintiff's narrative paragraph."
DEFENDANT_MSG = "Write a single defendant's narrative paragraph."

# === Polishing Helpers ===
def polish_section(text: str, context: str = "") -> str:
    """Polish each section for clarity, conciseness, and legal tone."""
    if not text.strip():
        return ""
    prompt = f"""
{FULL_SAFETY_PROMPT}

Polish this section of the mediation memo:
- Eliminate redundancy
- Maintain a formal, persuasive tone
- Use active voice
- Standardize titles (Mr./Ms.), citations, and punctuation
- Ensure section advances the argument

Context: {context}

Section:
{text}
"""
    return safe_generate(prompt=prompt, model="gpt-4")

def final_polish_memo(memo_data: dict) -> dict:
    """Perform a final full-memo polish to remove duplication and tighten flow."""
    joined = "\n\n".join([f"## {k}\n{v}" for k, v in memo_data.items()])
    prompt = f"""
{FULL_SAFETY_PROMPT}

Perform a full memo-wide polish:
1. Remove duplicated facts between sections (Parties, Facts/Liability, Conclusion).
2. Ensure smooth transitions and logical flow between sections.
3. Keep each section concise and impactful.
4. Standardize all party names, titles, and citations.

Memo:
{joined}
"""
    cleaned = safe_generate(prompt=prompt, model="gpt-4")
    # Split the cleaned text back into individual sections
    new_data = {}
    for section in memo_data.keys():
        marker = f"## {section}"
        if marker in cleaned:
            new_data[section] = cleaned.split(marker, 1)[-1].split("##", 1)[0].strip()
        else:
            new_data[section] = memo_data[section]
    return new_data

# === Quote Extraction ===
def generate_quotes_from_raw_depo(raw_text: str, categories: list) -> dict:
    """Extract and categorize quotes from deposition transcript text."""
    try:
        lines = normalize_deposition_lines(raw_text)
        qa_text = merge_multiline_qas(lines)
        chunks = [qa_text[i:i + 9000] for i in range(0, len(qa_text), 9000)]
        return generate_quotes_in_chunks(chunks, categories=categories)
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to extract quotes from deposition: {e}"))
        return {}

def curate_quotes_for_section(section_name: str, quotes: str, context: str) -> str:
    """Select the most relevant quotes for a section from a larger quote pool."""
    if not quotes.strip():
        return ""
    prompt = f"""
{FULL_SAFETY_PROMPT}

From these quotes:

{quotes}

Select up to 3 that are most relevant for **{section_name}**. 
Only return the exact quotes (no paraphrasing).

Context:
{context}
"""
    curated = safe_generate(prompt=prompt, model="gpt-4")
    return curated.strip()

# === Main Memo Generation ===
def generate_memo_from_fields(data: dict, template_path: str, output_dir: str) -> tuple:
    """Main orchestration of memo generation using GPT and template population."""
    try:
        memo_data = {}
        plaintiffs = data.get("plaintiffs", "")
        defendants = data.get("defendants", "")

        # Curate quotes
        liability_quotes = curate_quotes_for_section(
            "Facts & Liability", data.get("liability_quotes", ""), data.get('complaint_narrative', '')
        )
        damages_quotes = curate_quotes_for_section(
            "Harms & Losses", data.get("damages_quotes", ""), data.get('medical_summary', '')
        )

        # === Introduction ===
        intro_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Introduction (concise, persuasive, no duplicate facts):
Complaint Narrative: {data.get('complaint_narrative', '')}

Example:
{INTRO_EXAMPLE}
"""
        memo_data["Introduction"] = polish_section(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(intro_prompt, 3000),
            model="gpt-4", system_msg=INTRO_MSG
        )))

        # === Parties ===
        parties_prompt = f"""
{FULL_SAFETY_PROMPT}

Summarize all Plaintiffs and Defendants (roles only, no accident facts):
Party Info: {data.get('party_information_from_complaint', '')}

Example:
{PLAINTIFF_STATEMENT_EXAMPLE}
"""
        memo_data["Parties"] = polish_section(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(parties_prompt, 3000),
            model="gpt-4", system_msg=PARTIES_MSG
        )))

        # === Facts & Liability ===
        facts_prompt = f"""
{FULL_SAFETY_PROMPT}

Write the Facts & Liability section:
- Show duty, breach, causation clearly
- Embed at least 3 liability quotes inline

Narrative: {data.get('complaint_narrative', '')}
Liability Quotes: {liability_quotes}

Example:
{FACTS_LIABILITY_EXAMPLE}
"""
        memo_data["Facts_Liability"] = polish_section(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(facts_prompt, 3500),
            model="gpt-4", system_msg=FACTS_MSG
        )))

        # === Causation/Injuries ===
        causation_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft Causation/Injuries: link the accident to medical findings and treatment.

Medical Summary:
{data.get('medical_summary', '')}

Example:
{CAUSATION_EXAMPLE}
"""
        memo_data["Causation_Injuries_Treatment"] = polish_section(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(causation_prompt, 3000),
            model="gpt-4", system_msg=CAUSATION_MSG
        )))

        # === Harms & Losses ===
        harms_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft Harms & Losses:
- Demonstrate functional and emotional impact
- Tie injuries, life impact, and earning capacity together
- Embed at least 3 damages quotes inline

Medical Summary:
{data.get('medical_summary', '')}
Damages Quotes:
{damages_quotes}

Example:
{HARMS_EXAMPLE}
"""
        memo_data["Additional_Harms_Losses"] = polish_section(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(harms_prompt, 3000),
            model="gpt-4", system_msg=HARMS_MSG
        )))

        # === Future Medical Bills ===
        future_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft Future Medical Bills section: outline future care and associated costs.

Summary:
{data.get('future_medical_bills', '')}

Example:
{FUTURE_BILLS_EXAMPLE}
"""
        memo_data["Future_Medical_Bills"] = polish_section(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(future_prompt, 2500),
            model="gpt-4", system_msg=FUTURE_MSG
        )))

        # === Conclusion ===
        conclusion_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft a concise, strong Conclusion: 
- Restate settlement posture in 1-2 sentences
- Finish with litigation readiness

Settlement Summary:
{data.get('settlement_summary', '')}

Example:
{CONCLUSION_EXAMPLE}
"""
        memo_data["Conclusion"] = polish_section(run_in_thread(lambda: safe_generate(
            prompt=trim_to_token_limit(conclusion_prompt, 2500),
            model="gpt-4", system_msg=CONCLUSION_MSG
        )))

        # === Final Memo-Wide Polish ===
        memo_data = {k: html.unescape(v) for k, v in memo_data.items()}
        memo_data = final_polish_memo(memo_data)

        # Add static fields for template
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
    """Generate a plaintext version of the memo for preview."""
    try:
        sections = [
            "Introduction", "Parties", "Facts_Liability",
            "Causation_Injuries_Treatment", "Additional_Harms_Losses",
            "Future_Medical_Bills", "Conclusion"
        ]
        return "\n\n".join([
            f"## {s.replace('_', ' ')}\n\n{html.unescape(data.get(s, '').strip())}" 
            for s in sections
        ])
    except Exception as e:
        logger.error(redact_log(f"❌ Failed to generate plaintext memo: {e}"))
        return ""
