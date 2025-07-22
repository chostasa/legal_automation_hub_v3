from jinja2 import Environment, BaseLoader, select_autoescape
from prompts.banned_phrases import (
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    BAN_PHRASES_NOTE,
    FORBIDDEN_PHRASES,
    NO_PASSIVE_LANGUAGE_NOTE
)

# Setup Jinja2 with autoescape to prevent formatting or prompt injection
jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(enabled_extensions=("txt", "j2"))
)

BASE_PROMPT_TEMPLATE = """
{{ no_hallucination_note }}
{{ legal_fluency_note }}
{{ ban_phrases_note }}
{{ forbidden_phrases }}
{{ no_passive_note }}

You are drafting the **{{ section }}** section of a legal document for {{ client_name }}.

Only use the following facts and content:
{{ summary }}

{% if example %}
Use the following as a tone/style example:
{{ example }}
{% endif %}

{{ extra_instructions }}
""".strip()


def build_prompt(
    section: str,
    summary: str,
    client_name: str = "Jane Doe",
    extra_instructions: str = "",
    example: str = ""
) -> str:
    """
    Constructs a full, escaped prompt for GPT with best practices and safety notes.

    Args:
        section (str): Section name ("Demand", "Introduction", etc.)
        summary (str): The factual content to base the section on
        client_name (str): For reference in context
        extra_instructions (str): Additional custom behavior (quote embedding, tone)
        example (str): (Optional) Tone/style snippet (not copied, just influence)

    Returns:
        str: Rendered prompt string
    """
    template = jinja_env.from_string(BASE_PROMPT_TEMPLATE)

    return template.render(
        section=section,
        summary=summary.strip(),
        client_name=client_name.strip(),
        extra_instructions=extra_instructions.strip(),
        example=example.strip(),
        no_hallucination_note=NO_HALLUCINATION_NOTE,
        legal_fluency_note=LEGAL_FLUENCY_NOTE,
        ban_phrases_note=BAN_PHRASES_NOTE,
        forbidden_phrases=FORBIDDEN_PHRASES,
        no_passive_note=NO_PASSIVE_LANGUAGE_NOTE,
    )
