from jinja2 import Environment, BaseLoader, select_autoescape

# === Demand Prompts ===
from core.prompts.demand_guidelines import (
    NO_HALLUCINATION_NOTE as DEMAND_NO_HALLUCINATION,
    LEGAL_FLUENCY_NOTE as DEMAND_LEGAL_FLUENCY,
    STRUCTURE_GUIDE_NOTE as DEMAND_STRUCTURE,
    LEGAL_TRANSITION_NOTE as DEMAND_TRANSITION,
    NO_PASSIVE_LANGUAGE_NOTE as DEMAND_NO_PASSIVE,
    BAN_PHRASES_NOTE as DEMAND_BAN_PHRASES,
)
from core.prompts.demand_example import EXAMPLE_DEMAND, SETTLEMENT_EXAMPLE

# === FOIA Prompts ===
from core.prompts.foia_guidelines import (
    FULL_SAFETY_PROMPT as FOIA_SAFETY_PROMPT,
    FOIA_BULLET_POINTS_PROMPT_TEMPLATE,
    FOIA_SYNOPSIS_PROMPT,
)
from core.prompts.foia_example import FOIA_BULLET_POINTS_EXAMPLES

# === Memo Prompts ===
from core.prompts.memo_guidelines import FULL_SAFETY_PROMPT as MEMO_SAFETY_PROMPT
from core.prompts.memo_examples import (
    INTRO_EXAMPLE,
    PLAINTIFF_STATEMENT_EXAMPLE,
    DEFENDANT_STATEMENT_EXAMPLE,
    DEMAND_EXAMPLE as MEMO_DEMAND_EXAMPLE,
    FACTS_LIABILITY_EXAMPLE,
    CAUSATION_EXAMPLE,
    HARMS_EXAMPLE,
    FUTURE_BILLS_EXAMPLE,
    CONCLUSION_EXAMPLE,
)

# === Style Transfer Prompts ===
from core.prompts.style_transfer import build_style_transfer_prompt

# Setup Jinja2
jinja_env = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(enabled_extensions=("txt", "j2"))
)

# === Base Template for Demand & Memo ===
BASE_PROMPT_TEMPLATE = """
{{ safety_notes }}

You are drafting the **{{ section }}** section for {{ client_name }}.

Facts and content to use:
{{ summary }}

{% if example %}
Use the following as a tone/style example:
{{ example }}
{% endif %}

{{ extra_instructions }}
""".strip()

def build_prompt(
    prompt_type: str,
    section: str,
    summary: str,
    client_name: str = "Jane Doe",
    extra_instructions: str = "",
    example: str = ""
) -> str:
    """
    Constructs a full prompt string for GPT based on prompt_type.

    Args:
        prompt_type (str): "demand", "foia", "memo", or "style_transfer"
        section (str): Section name
        summary (str): The factual content
        client_name (str): Client name reference
        extra_instructions (str): Extra instructions (quote embedding, bulleting, etc.)
        example (str): Example text for tone/style
    """

    if prompt_type == "demand":
        safety_notes = "\n\n".join([
            DEMAND_NO_HALLUCINATION,
            DEMAND_LEGAL_FLUENCY,
            DEMAND_STRUCTURE,
            DEMAND_TRANSITION,
            DEMAND_NO_PASSIVE,
            DEMAND_BAN_PHRASES
        ])
        template = jinja_env.from_string(BASE_PROMPT_TEMPLATE)
        return template.render(
            safety_notes=safety_notes,
            section=section,
            summary=summary.strip(),
            client_name=client_name.strip(),
            example=example.strip() or EXAMPLE_DEMAND,
            extra_instructions=extra_instructions.strip(),
        )

    elif prompt_type == "memo":
        template = jinja_env.from_string(BASE_PROMPT_TEMPLATE)
        return template.render(
            safety_notes=MEMO_SAFETY_PROMPT,
            section=section,
            summary=summary.strip(),
            client_name=client_name.strip(),
            example=example.strip(),
            extra_instructions=extra_instructions.strip(),
        )

    elif prompt_type == "foia":
        # FOIA uses its own structured templates
        return FOIA_BULLET_POINTS_PROMPT_TEMPLATE.format(
            case_synopsis=summary,
            case_type=section,
            facility="facility/system info",
            defendant_role="defendant role",
            explicit_instructions=extra_instructions,
            potential_requests=FOIA_BULLET_POINTS_EXAMPLES
        )

    elif prompt_type == "style_transfer":
        # Use the dedicated style transfer builder
        examples = example.split("---") if example else []
        return build_style_transfer_prompt(examples, summary)

    else:
        raise ValueError(f"Unknown prompt_type: {prompt_type}")
