NO_HALLUCINATION_NOTE = """
Do not fabricate or assume any facts. Only use what is explicitly provided in the case synopsis or instructions.
"""

LEGAL_FLUENCY_NOTE = """
Use the tone and clarity of a senior litigator. Maintain precise legal language and context-appropriate tone.
"""

NO_PASSIVE_LANGUAGE_NOTE = """
Every sentence must use active voice. Do not rely on vague or passive constructions.
"""

BAN_PHRASES_NOTE = """
Avoid any speculative or weak language. Do not include dates, case numbers, or facts not in the provided case synopsis.
Do not pull facts, names, or numbers from any style examples — they are for tone and structure only.
"""

FULL_SAFETY_PROMPT = "\n\n".join([
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
    BAN_PHRASES_NOTE,
])


FOIA_BULLET_POINTS_PROMPT_TEMPLATE = """
{full_safety}

You are drafting FOIA bullet points for a civil legal claim.

Case synopsis:
{case_synopsis}

Case type: {case_type}
Facility or system involved: {facility}
Defendant role: {defendant_role}

Explicit instructions:
{explicit_instructions}

Common requests or priorities:
{potential_requests}

Now draft a detailed and **role-specific** list of records, documents, media, and internal communications that a skilled civil attorney would request from this type of facility or entity.

DO NOT fabricate or assume facts.
DO NOT include dates, case numbers, or details from any example material — examples are for tone only.

Format output as Word-style bullet points using asterisks (*).
Only return the list.
""".strip().format(full_safety=FULL_SAFETY_PROMPT)


FOIA_SYNOPSIS_PROMPT = """
{full_safety}

Summarize the following case background in exactly 2 sentences:
1. First sentence: describe what happened.
2. Second sentence: describe the resulting harm or damages.

DO NOT use bullet points, lists, or include any names, dates, case numbers, or personal identifiers.
DO NOT pull facts or details from examples — only use the text below.

Case synopsis:
{case_synopsis}
""".strip().format(full_safety=FULL_SAFETY_PROMPT)
