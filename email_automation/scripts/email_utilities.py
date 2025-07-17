# email_utilities.py

import os
from jinja2 import Template
from email_automation.config import TEMPLATE_CONFIG

def load_template(template_key):
    config = TEMPLATE_CONFIG[template_key]
    with open(config["template_file"], "r", encoding="utf-8") as file:
        content = file.read()
    return content, config["subject"], config["cc"]

def merge_template(template_key, client_data):
    body_raw, subject_template, cc_list = load_template(template_key)

    # Fill placeholders
    merged_body = Template(body_raw).render(**client_data)
    merged_subject = Template(subject_template).render(**client_data)

    return merged_subject, merged_body, cc_list
