import re
from string import Template
from core.error_handling import handle_error
from core.security import mask_phi, redact_log

def render_docx_placeholders(text: str, context: dict) -> str:
    """
    Safely replace placeholders in text using Python's Template.
    Example: "Hello {{ClientName}}" → "Hello Jane"
    """
    normalized = re.sub(r"\{\{(.*?)\}\}", r"${\1}", text)

    try:
        return Template(normalized).safe_substitute(context)
    except KeyError:
        return re.sub(r"\$\{[^{}]+\}", "", normalized)
    except Exception as e:
        handle_error(
            e,
            code="TEMPLATE_ENGINE_001",
            message="Failed to render placeholders in template.",
            context=redact_log(mask_phi(f"text={text[:100]}"))
        )
        return ""
