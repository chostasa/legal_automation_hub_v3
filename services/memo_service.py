import os
import html
from core.security import sanitize_text, redact_log, mask_phi
from core.error_handling import handle_error
from utils.docx_utils import replace_text_in_docx_all
from services.openai_client import safe_generate
from utils.token_utils import trim_to_token_limit
from utils.thread_utils import run_in_thread
from logger import logger
from core.usage_tracker import check_quota_and_decrement
from core.auth import get_tenant_id

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

INTRO_MSG = "Draft a concise, persuasive Introduction."
PARTIES_MSG = "Summarize parties' roles without redundancy."
PLAINTIFF_MSG = "Write a single plaintiff's role-based paragraph."
DEFENDANT_MSG = "Write a single defendant's role-based paragraph."
FACTS_MSG = "Draft a forceful Facts & Liability section."
CAUSATION_MSG = "Draft a clear Causation & Injuries section."
HARMS_MSG = "Draft a persuasive Harms & Losses section showing impact."
FUTURE_MSG = "Draft the Future Medical Expenses section."
CONCLUSION_MSG = "Draft a strong Conclusion with litigation readiness."

def polish_section(text: str, context: str = "", test_mode: bool = False) -> str:
    if not text.strip():
        return ""
    try:
        if test_mode:
            return text.strip()
        prompt = f"""
{FULL_SAFETY_PROMPT}

Polish this section of the mediation memo:
- Remove any redundancy and overly dense paragraphs
- Ensure paragraphs are 2–4 sentences each for readability
- Strengthen transitions and narrative flow
- Maintain a formal, persuasive, senior-litigator tone
- Use active voice and standardized citations (Ex. A, Name Dep. [Line])

Context: {context}

Section:
{text}
"""
        return safe_generate(prompt=prompt, model="gpt-4")
    except Exception as e:
        handle_error(e, code="MEMO_POLISH_001", user_message="Failed to polish memo section.")
        return text

def final_polish_memo(memo_data: dict, test_mode: bool = False) -> dict:
    try:
        if test_mode:
            return memo_data
        joined = "\n\n".join([f"## {k}\n{v}" for k, v in memo_data.items()])
        prompt = f"""
{FULL_SAFETY_PROMPT}

Perform a final, full-memo polish:
1. Remove any duplicated facts or injuries between sections (Intro, Parties, Facts, Harms, Conclusion).
2. Break up dense paragraphs (2–4 sentences each).
3. Ensure smooth transitions between sections using strong connective language.
4. Tie damages and future medical costs directly to the client's quality of life and earning capacity.
5. Ensure the Parties section fully introduces all Plaintiffs and Defendants.
6. Standardize citations (Ex. A, Name Dep. [Line]) and correct any special character issues.

Memo:
{joined}
"""
        cleaned = safe_generate(prompt=prompt, model="gpt-4")
        new_data = {}
        for section in memo_data.keys():
            marker = f"## {section}"
            if marker in cleaned:
                new_data[section] = cleaned.split(marker, 1)[-1].split("##", 1)[0].strip()
            else:
                new_data[section] = memo_data[section]
        return new_data
    except Exception as e:
        handle_error(e, code="MEMO_POLISH_002", user_message="Final polish failed. Returning unpolished memo.")
        return memo_data

def generate_quotes_from_raw_depo(raw_text: str, categories: list, test_mode: bool = False) -> dict:
    try:
        if test_mode:
            return {cat.lower().replace(" ", "_") + "_quotes": "Test Quote" for cat in categories}
        lines = normalize_deposition_lines(raw_text)
        qa_text = merge_multiline_qas(lines)
        chunks = [qa_text[i:i + 9000] for i in range(0, len(qa_text), 9000)]
        return generate_quotes_in_chunks(chunks, categories=categories)
    except Exception as e:
        handle_error(e, code="MEMO_QUOTES_001", user_message="Failed to extract quotes from deposition.")
        return {}

def curate_quotes_for_section(section_name: str, quotes: str, context: str, test_mode: bool = False) -> str:
    if not quotes.strip():
        return ""
    try:
        if test_mode:
            return quotes.strip()
        prompt = f"""
{FULL_SAFETY_PROMPT}

From these quotes:

{quotes}

Select up to 3 that are most relevant for **{section_name}**. 
Only return the exact quotes (no paraphrasing).
Make sure each selected quote directly supports the section's legal or factual argument.

Context:
{context}
"""
        curated = safe_generate(prompt=prompt, model="gpt-4")
        return curated.strip()
    except Exception as e:
        handle_error(e, code="MEMO_QUOTES_002", user_message=f"Failed to curate quotes for {section_name}.")
        return ""

def generate_memo_from_fields(data: dict, template_path: str, output_dir: str, test_mode: bool = False) -> tuple:
    try:
        if not template_path or not os.path.exists(template_path):
            handle_error(
                FileNotFoundError(f"Template not found at {template_path}"),
                code="MEMO_TEMPLATE_001",
                user_message="Memo template is missing or inaccessible.",
                raise_it=True
            )

        tenant_id = get_tenant_id()
        check_quota_and_decrement(tenant_id, "memo_generation")

        memo_data = {}
        plaintiffs = data.get("plaintiffs", "")
        defendants = data.get("defendants", "")

        liability_quotes = curate_quotes_for_section(
            "Facts & Liability", data.get("liability_quotes", ""), data.get('complaint_narrative', ''), test_mode=test_mode
        )
        damages_quotes = curate_quotes_for_section(
            "Harms & Losses", data.get("damages_quotes", ""), data.get('medical_summary', ''), test_mode=test_mode
        )

        intro_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Introduction:
- Concisely frame case value and posture in 1–2 paragraphs
- Do not repeat facts later covered in Facts/Liability
- Avoid medical detail or redundant accident description

Complaint Narrative:
{data.get('complaint_narrative', '')}

Example:
{INTRO_EXAMPLE}
"""
        memo_data["Introduction"] = polish_section(
            run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(intro_prompt, 3000), model="gpt-4", system_msg=INTRO_MSG)),
            test_mode=test_mode
        )

        parties_block = []
        for i in range(1, 4):
            name = data.get(f"plaintiff{i}", "").strip()
            if name:
                plaintiff_prompt = f"""
{FULL_SAFETY_PROMPT}

Write a short, 1–2 sentence role-based paragraph for Plaintiff {name}:
- Clearly state their role and significance
- Avoid accident details or injuries (covered elsewhere)

Party Info:
{data.get('party_information_from_complaint', '')}

Example:
{PLAINTIFF_STATEMENT_EXAMPLE}
"""
                memo_data[f"Plaintiff_{i}"] = polish_section(
                    run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(plaintiff_prompt, 2500), model="gpt-4", system_msg=PLAINTIFF_MSG)),
                    test_mode=test_mode
                )
                parties_block.append(memo_data[f"Plaintiff_{i}"])
            else:
                memo_data[f"Plaintiff_{i}"] = ""

        for i in range(1, 8):
            name = data.get(f"defendant{i}", "").strip()
            if name:
                defendant_prompt = f"""
{FULL_SAFETY_PROMPT}

Write a short, 1–2 sentence role-based paragraph for Defendant {name}:
- Explain their corporate role and responsibilities in the case
- Avoid repeating accident details from Facts/Liability

Defendant Info:
{data.get('party_information_from_complaint', '')}

Example:
{DEFENDANT_STATEMENT_EXAMPLE}
"""
                memo_data[f"Defendant_{i}"] = polish_section(
                    run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(defendant_prompt, 2500), model="gpt-4", system_msg=DEFENDANT_MSG)),
                    test_mode=test_mode
                )
                parties_block.append(memo_data[f"Defendant_{i}"])
            else:
                memo_data[f"Defendant_{i}"] = ""

        parties_prompt = f"""
{FULL_SAFETY_PROMPT}

Combine the following party paragraphs into a cohesive "Parties" section:
{chr(10).join(parties_block)}

Ensure:
- Logical flow and smooth transitions
- No redundancy or repetition of accident details
"""
        memo_data["Parties"] = polish_section(
            run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(parties_prompt, 3000), model="gpt-4", system_msg=PARTIES_MSG)),
            test_mode=test_mode
        )

        facts_prompt = f"""
{FULL_SAFETY_PROMPT}

Write the Facts & Liability section:
- Establish duty, breach, and causation clearly
- Embed at least 3 liability quotes inline with context and proper citations
- Avoid repeating injuries or parties info already covered

Complaint Narrative:
{data.get('complaint_narrative', '')}
Liability Quotes:
{liability_quotes}

Example:
{FACTS_LIABILITY_EXAMPLE}
"""
        memo_data["Facts_Liability"] = polish_section(
            run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(facts_prompt, 3500), model="gpt-4", system_msg=FACTS_MSG)),
            test_mode=test_mode
        )

        causation_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Causation/Injuries section:
- Link facts to injuries and treatment progression clearly
- Avoid repeating accident narrative in full
- Keep paragraphs focused and persuasive

Medical Summary:
{data.get('medical_summary', '')}

Example:
{CAUSATION_EXAMPLE}
"""
        memo_data["Causation_Injuries_Treatment"] = polish_section(
            run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(causation_prompt, 3000), model="gpt-4", system_msg=CAUSATION_MSG)),
            test_mode=test_mode
        )

        harms_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Harms & Losses section:
- Show the professional, functional, and emotional impact persuasively
- Connect injuries to loss of earning capacity and diminished quality of life
- Embed at least 3 damages quotes inline with context and citations

Medical Summary:
{data.get('medical_summary', '')}
Damages Quotes:
{damages_quotes}

Example:
{HARMS_EXAMPLE}
"""
        memo_data["Additional_Harms_Losses"] = polish_section(
            run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(harms_prompt, 3000), model="gpt-4", system_msg=HARMS_MSG)),
            test_mode=test_mode
        )

        future_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Future Medical Bills section:
- Outline expected care and costs
- Explain how these expenses will affect the client's quality of life and independence
- Keep concise and persuasive

Future Care Summary:
{data.get('future_medical_bills', '')}

Example:
{FUTURE_BILLS_EXAMPLE}
"""
        memo_data["Future_Medical_Bills"] = polish_section(
            run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(future_prompt, 2500), model="gpt-4", system_msg=FUTURE_MSG)),
            test_mode=test_mode
        )

        conclusion_prompt = f"""
{FULL_SAFETY_PROMPT}

Draft the Conclusion:
- Summarize settlement posture in 1–2 sentences
- Do not repeat facts or injuries
- End with firm litigation-readiness language

Settlement Summary:
{data.get('settlement_summary', '')}

Example:
{CONCLUSION_EXAMPLE}
"""
        memo_data["Conclusion"] = polish_section(
            run_in_thread(lambda: safe_generate(prompt=trim_to_token_limit(conclusion_prompt, 2500), model="gpt-4", system_msg=CONCLUSION_MSG)),
            test_mode=test_mode
        )

        memo_data = {k: html.unescape(v) for k, v in memo_data.items()}
        memo_data = final_polish_memo(memo_data, test_mode=test_mode)

        memo_data.update({
            "Court": html.unescape(data.get("court", "")),
            "Case_Number": html.unescape(data.get("case_number", "")),
            "Plaintiffs": html.unescape(plaintiffs),
            "Defendants": html.unescape(defendants),
            "Demand": html.unescape(data.get("settlement_summary", ""))
        })

        output_path = os.path.join(output_dir, f"Mediation_Memo_{plaintiffs or 'Unknown'}.docx")
        if not test_mode:
            run_in_thread(replace_text_in_docx_all, template_path, memo_data, output_path)
        else:
            output_path = os.path.join(output_dir, "Test_Mediation_Memo.docx")

        if not os.path.exists(output_path) and not test_mode:
            handle_error(
                RuntimeError("Memo DOCX not created."),
                code="MEMO_OUTPUT_001",
                user_message="Mediation Memo DOCX could not be created.",
                raise_it=True
            )

        return output_path, memo_data

    except Exception as e:
        handle_error(
            e,
            code="MEMO_GEN_001",
            user_message="Memo generation failed.",
            raise_it=True
        )

def generate_plaintext_memo(data: dict) -> str:
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
        handle_error(
            e,
            code="MEMO_PREVIEW_001",
            user_message="Failed to generate plaintext memo preview."
        )
        return ""