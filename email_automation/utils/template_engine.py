import os

def merge_template(template_key: str, replacements: dict) -> tuple[str, str, list[str]]:
    """
    Loads a .txt or .html template and substitutes {{placeholders}} with values from replacements.

    Template format (for .txt):
    Subject: Welcome {{ClientName}}
    Body:
    Hello {{ClientName}}, welcome...

    Template format (for .html):
    Subject: Welcome {{ClientName}}
    Body:
    <html> ... HTML content with {{placeholders}} ... </html>

    Returns: (subject, body, cc_list)
    """

    # Locate template (.txt or .html)
    possible_paths = [
        os.path.join("email_automation", "templates", f"{template_key}.html"),
        os.path.join("email_automation", "templates", f"{template_key}.txt")
    ]
    template_path = next((p for p in possible_paths if os.path.exists(p)), None)

    if not template_path:
        raise FileNotFoundError(f"Template '{template_key}' not found as .html or .txt")

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Ensure it has Subject and Body sections
    if "Subject:" not in content or "Body:" not in content:
        raise ValueError("Template must contain both 'Subject:' and 'Body:' sections")

    # Split into subject and body
    subject_line = content.split("Subject:")[1].split("Body:")[0].strip()
    body_content = content.split("Body:")[1].strip()

    # Replace placeholders {{key}} with values
    for key, value in replacements.items():
        subject_line = subject_line.replace(f"{{{{{key}}}}}", str(value))
        body_content = body_content.replace(f"{{{{{key}}}}}", str(value))

    # Build CC list if ReferringAttorneyEmail exists
    cc_list = [replacements.get("ReferringAttorneyEmail", "")] if "ReferringAttorneyEmail" in replacements else []

    return subject_line, body_content, cc_list
