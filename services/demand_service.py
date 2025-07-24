import os
import html
from datetime import datetime
from docx import Document
from openpyxl import load_workbook
from openai import OpenAI

# === OpenAI Setup ===
client = OpenAI()

# === OpenAI Completion Helper ===
def generate_with_openai(prompt):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional legal writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return html.unescape(response.choices[0].message.content.strip())

# === Section Generators with Style Examples Injected ===

from core.prompts.demand_guidelines import FULL_SAFETY_PROMPT
from core.prompts.demand_example import EXAMPLE_DEMAND, SETTLEMENT_EXAMPLE
from core.prompts.demand_guidelines import STRUCTURE_GUIDE_NOTE
from core.gpt.open_ai import safe_generate

def generate_brief_synopsis(summary, full_name, example_text=None):
    prompt = f"""
{FULL_SAFETY_PROMPT}
{STRUCTURE_GUIDE_NOTE}

Write a one-sentence introduction for a legal demand letter.
Begin with: \"Our office represents {full_name}, who suffered...\"
and describe the injuries factually and concisely. Do not repeat the client's name.
Use clinical, direct phrasing.

Summary of Incident:
{summary}
"""
    return safe_generate(prompt).split(".")[0].strip() + "."

def generate_combined_facts(summary, first_name, example_text=None):
    prompt = f"""
{FULL_SAFETY_PROMPT}
{STRUCTURE_GUIDE_NOTE}

Below is an example of a professionally written liability paragraph. Use it **only** to mirror tone, fluency, and structure:
---
{(example_text or EXAMPLE_DEMAND).strip()}
---

Now write a persuasive, fluent paragraph that presents liability for {first_name}, focusing on:
- Duty of care
- Breach of duty
- Causation
- Resulting harm

Avoid headings. Do not re-list injuries. Assume summary below provides facts:

Summary:
{summary}
"""
    return safe_generate(prompt)

def generate_combined_damages(damages_text, first_name, example_text=None):
    prompt = f"""
{FULL_SAFETY_PROMPT}
{STRUCTURE_GUIDE_NOTE}

Write a professional, medically grounded paragraph describing the aftermath of the injuries suffered by {first_name}.
Focus on:
- Disruption to care and recovery
- Financial and occupational hardship
- Emotional and psychological toll

Avoid re-describing physical injuries. Frame all impacts in terms of ongoing consequences.
Do not reference the incident again — focus only on aftermath.

Damages Summary:
{damages_text}
"""
    return safe_generate(prompt)

def generate_settlement_demand(summary, damages, first_name, example_text=None):
    prompt = f"""
{FULL_SAFETY_PROMPT}
{STRUCTURE_GUIDE_NOTE}

Use the following paragraph ONLY as a tone/style guide — do not use any facts from it:
---
{(example_text or SETTLEMENT_EXAMPLE).strip()}
---

Write the final paragraph of a legal demand letter for {first_name}. Justify settlement based on the facts and harms described above.
Include:
- Clear, confident summary of liability
- Anticipated discovery support
- Litigation risk if unresolved
- A formal call to resolve: “We invite resolution of this matter without the need for formal litigation...”

Do not introduce new facts or speculative claims.

Summary:
{summary}

Damages:
{damages}
"""
    return safe_generate(prompt)


# === Template Replacement ===
def replace_placeholders(doc, replacements):
    for paragraph in doc.paragraphs:
        text = paragraph.text
        for key, val in replacements.items():
            if key in text:
                text = text.replace(key, val)
        if paragraph.runs:
            paragraph.clear()
            paragraph.add_run(text)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    text = paragraph.text
                    for key, val in replacements.items():
                        if key in text:
                            text = text.replace(key, val)
                    if paragraph.runs:
                        paragraph.clear()
                        paragraph.add_run(text)

# === Template Filler ===
def fill_template(data, template_path, output_dir):
    doc = Document(template_path)

    full_name = data.get("Client Name", "").strip()
    first_name = full_name.strip().split()[0] if full_name.strip() else "Client"

    incident_date = data.get("IncidentDate", "")
    if isinstance(incident_date, datetime):
        incident_date = incident_date.strftime("%B %d, %Y")
    elif not incident_date:
        incident_date = "[Date not provided]"

    summary = data.get("Summary", "[No summary provided.]")
    damages = data.get("Damages", "[No damages provided.]")

    replacements = {
        "{{RecipientName}}": data.get("RecipientName", "[Recipient Name]"),
        "{{ClientName}}": full_name,
        "{{IncidentDate}}": incident_date,
        "{{BriefSynopsis}}": generate_brief_synopsis(summary, full_name),
        "{{Demand}}": generate_combined_facts(summary, first_name),
        "{{Damages}}": generate_combined_damages(damages, first_name),
        "{{SettlementDemand}}": generate_settlement_demand(summary, damages, first_name),
}

    replace_placeholders(doc, replacements)

    output_filename = f"Demand_{full_name.replace(' ', '_')}_{datetime.today().strftime('%Y-%m-%d')}.docx"
    output_path = os.path.join(output_dir, output_filename)
    doc.save(output_path)
    return output_path

# === Excel Integration ===
def generate_all_demands(template_path, excel_path, output_dir):
    wb = load_workbook(excel_path)
    sheet = wb.active
    headers = [str(cell.value).strip() for cell in sheet[1]]
    os.makedirs(output_dir, exist_ok=True)

    for row in sheet.iter_rows(min_row=2, values_only=True):
        data = dict(zip(headers, row))
        if not data.get("Client Name", "").strip():
            continue
        fill_template(data, template_path, output_dir)

# === UI-compatible wrapper ===
def generate_demand_letter(
    client_name,
    defendant,
    location,
    incident_date,
    summary,
    damages,
    template_path,
    output_path,
    example_text=None
):
    data = {
        "Client Name": client_name,
        "Defendant": defendant,
        "Location": location,
        "IncidentDate": incident_date,
        "Summary": summary,
        "Damages": damages,
        "RecipientName": defendant,
        "Example Text": example_text or ""
    }

    return output_path, fill_template(data, template_path, os.path.dirname(output_path))

# === Main Runner for Local Use ===
if __name__ == "__main__":
    TEMPLATE_PATH = "templates/demand_template.docx"
    EXCEL_PATH = "data_demand_requests.xlsx"
    OUTPUT_DIR = "output_requests"
    generate_all_demands(TEMPLATE_PATH, EXCEL_PATH, OUTPUT_DIR)
