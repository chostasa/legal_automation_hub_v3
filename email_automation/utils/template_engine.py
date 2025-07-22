import os

def merge_template(template_key: str, replacements: dict) -> tuple[str, str, list[str]]:
    """
    Loads a .txt template and substitutes {{placeholders}} with values from replacements.

    Template format:
    Subject: Welcome {{ClientName}}
    Body:
    Hello {{ClientName}}, welcome...

    Returns: (subject, body, cc_list)
    """
    template_path = os.path.join("email_automation", "templates", f"{template_key}.txt")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "Subject:" not in content or "Body:" not in content:
        raise ValueError("Template must contain both 'Subject:' and 'Body:' sections")

    subject_line = content.split("Subject:")[1].split("Body:")[0].strip()
    body_content = content.split("Body:")[1].strip()

    for key, value in replacements.items():
        subject_line = subject_line.replace(f"{{{{{key}}}}}", str(value))
        body_content = body_content.replace(f"{{{{{key}}}}}", str(value))

    cc_list = [replacements.get("ReferringAttorneyEmail", "")] if "ReferringAttorneyEmail" in replacements else []

    return subject_line, body_content, cc_list
