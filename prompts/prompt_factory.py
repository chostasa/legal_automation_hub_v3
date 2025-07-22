from prompts.banned_phrases import (
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    BAN_PHRASES_NOTE, 
    FORBIDDEN_PHRASES,
    NO_PASSIVE_LANGUAGE_NOTE
)

def build_prompt(
    section: str,
    summary: str,
    client_name: str = "Jane Doe",
    extra_instructions: str = "",
    example: str = ""
) -> str:
    """
    Constructs a full prompt for GPT with best practices and safety notes.
    
    Args:
        section (str): Section name ("Demand", "Introduction", etc.)
        summary (str): The factual content to base the section on
        client_name (str): For reference if needed
        extra_instructions (str): Tool-specific additions (e.g., quote embedding)
        example (str): (Optional) Style guide example (not for copying)

    Returns:
        str: Full prompt string
    """

    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}
{BAN_PHRASES_NOTE}
{FORBIDDEN_PHRASES}
{NO_PASSIVE_LANGUAGE_NOTE}

You are drafting the **{section}** section of a legal document for {client_name}.

Only use the following facts and content:

{summary.strip()}

{f'Use the following as a tone/style example:\n{example}' if example else ''}
{extra_instructions}
""".strip()

    return prompt
