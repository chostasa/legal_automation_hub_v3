from jinja2 import Environment, BaseLoader
import re

def render_template_string(template_str: str, context: dict) -> str:
    env = Environment(loader=BaseLoader(), autoescape=True)
    template = env.from_string(template_str)
    return template.render(**context)

def render_docx_placeholders(text: str, context: dict) -> str:
    rendered = render_template_string(text, context)
    return re.sub(r"{{[^{}]+}}", "", rendered)  
