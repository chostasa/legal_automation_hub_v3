import os
import html
from datetime import datetime
from docx import Document
from openpyxl import load_workbook
from openai import OpenAI

# === OpenAI Setup ===
client = OpenAI()

# === Prompt Safety Notes ===
NO_HALLUCINATION_NOTE = """
Do not fabricate or assume any facts. Use only what is provided. Avoid headings, greetings, and signoffs — the template handles those. Refer to the client by their first name only. Keep all naming, pronouns, and chronology consistent. Do not use more than one version of the incident. Do not repeat injury or treatment details across sections.
"""

LEGAL_FLUENCY_NOTE = """
Use the tone and clarity of a senior litigator. Frame facts persuasively using legal reasoning: duty, breach, causation, and harm. Eliminate redundancy, vague phrases, and casual storytelling. Frame liability clearly. Maintain formal, polished, and precise language. Quantify damages where possible. Refer to witnesses, police, and footage once.
Do not restate the client’s injuries more than once. After the initial mention, refer to them only by category.
"""

FULL_SAFETY_PROMPT = "\n\n".join([NO_HALLUCINATION_NOTE.strip(), LEGAL_FLUENCY_NOTE.strip()])

# === OpenAI Completion Helper ===
def generate_with_openai(prompt):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a professional legal writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return html.unescape(response.choices[0].message.content.strip())

# === Section Generators ===
def generate_brief_synopsis(summary, full_name):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write a one-sentence introduction for a legal demand letter. Refer to the client only as {full_name}. Begin with a sentence like: "Our office represents {full_name}, who suffered..." and describe the injuries factually and concisely. Do not repeat the client's name. Do not use more than one sentence.

Summary of Incident:
{summary}
"""
    first_sentence = generate_with_openai(prompt).split(".")[0].strip() + "."
    return first_sentence

def generate_combined_facts(summary, first_name):
    prompt = f"""{FULL_SAFETY_PROMPT}

Write a single, polished paragraph that incorporates:
- duty,
- standard of care,
- breach,
- causation,
- and harm.

This is for a legal demand letter for a client named {first_name}. Do not label the sections. Do not repeat injuries verbatim from the summary — reference them categorically instead (e.g., orthopedic trauma, psychological harm, etc.).

Summary:
{summary}
"""
    return generate_with_openai(prompt)

def generate_combined_damages(damages_text, first_name):
    prompt = f"""{FULL_SAFETY_PROMPT}

Write a single flowing paragraph describing the damages suffered by {first_name}. Include:
- medical disruption,
- treatment efforts,
- financial strain,
- and emotional hardship.

Do not use section titles. Do not repeat injury descriptions. Keep the tone formal and persuasive.

Damages Summary:
{damages_text}
"""
    return generate_with_openai(prompt)

def generate_settlement_demand(summary, damages, first_name):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Use a professional, authoritative tone. Avoid casual or speculative phrasing. Do not invent any facts or sources of liability. Do not reference things like "bus footage" or "witnesses" unless explicitly provided.

Draft a closing settlement paragraph for {first_name} that justifies the demand based on the facts and injuries described below. Do not add any legal theories or damages not mentioned. Reference the strength of clients position based on factual consistency, corroborating sources, and the nature of their injuries.

Refine tone to remove informality and literary phrasing.

Where possible, preview anticipated evidence more confidently (e.g., “anticipated to show…” vs. “might show…”).

Condense repetitive phrasing. 

Make the transitions and flow fluent. 

Trim redundancy.

Avoid redundancy.

Integrate a single strong sentence on why litigation risk is high if this isn’t resolved.

End with a direct call to action: “We invite resolution of this matter without the need for formal litigation. Should you fail to respond by [insert date], we are prepared to proceed accordingly.”

Summary:
{summary}

Damages:
{damages}
"""
    return generate_with_openai(prompt)


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
    first_name = full_name.split()[0] if full_name else "Client"

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
