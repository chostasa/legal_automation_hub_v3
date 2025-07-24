NO_HALLUCINATION_NOTE = """
Do not fabricate or assume any facts. Use only what is provided. Avoid headings, greetings, and signoffs — the template handles those. Refer to the client by their first name only. Keep all naming, pronouns, and chronology consistent. Do not use more than one version of the incident. Do not repeat injury or treatment details across sections.
"""

STRUCTURE_GUIDE_NOTE = """
Use clear, logical structure to organize the letter sections. Follow legal analysis order: duty, breach, causation, harm. Ensure paragraphs flow smoothly and persuasively without redundant repetition.
"""

LEGAL_FLUENCY_NOTE = """
Use the tone and clarity of a senior litigator. Frame facts persuasively using legal reasoning: duty, breach, causation, and harm. Eliminate redundancy, vague phrases, and casual storytelling. Frame liability clearly. Maintain formal, polished, and precise language. Quantify damages where possible. Refer to witnesses, police, and footage once.
Do not restate the client’s injuries more than once. After the initial mention, refer to them only by category (e.g., orthopedic trauma, neurological symptoms).
"""

NO_PASSIVE_LANGUAGE_NOTE = """
Every sentence must use active voice. Eliminate passive constructions. Do not say “was struck” — say “The snowplow struck Jane.”
"""

BAN_PHRASES_NOTE = """
Avoid any speculative or weak language: “may,” “might,” “potential,” “appears to,” “possibly,” “believes that.”
Instead, use: “is,” “will show,” “depicts,” “demonstrates.”
"""

FULL_SAFETY_PROMPT = "\n\n".join([
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
    BAN_PHRASES_NOTE
])
