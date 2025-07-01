mport os
from datetime import datetime
from docx import Document
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from openai import OpenAI
import streamlit as st
from openpyxl import load_workbook

api_key = st.secrets["OPENAI_API_KEY"]
client = OpenAI(api_key=api_key)

def generate_with_openai(prompt):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a professional legal writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()
# === CONFIG ===
INPUT_FILE = 'data_foia_requests.xlsx'
TEMPLATE_FILE = 'templates_foia_template.docx'
OUTPUT_FOLDER = 'output_requests'
API_KEY_FILE = 'Open AI Secret Key.txt'

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# === LOAD API KEY ===
def load_api_key():
    with open(API_KEY_FILE, "r") as f:
        return f.read().strip()

# === PROMPT BUILDING ===
def build_prompt(case_synopsis, potential_requests, explicit_instructions, case_type, facility, defendant_role):
    return f"""
You are drafting FOIA bullet points for a civil legal claim.

Case synopsis:
{case_synopsis}

Case type: {case_type}
Facility or system involved: {facility}
Defendant role: {defendant_role}

Explicit instructions:
{explicit_instructions or "None provided"}

Common requests or priorities:
{potential_requests}

Please return a detailed and **role-specific** list of records, documents, media, and internal communications that a skilled civil attorney would request from this type of facility or entity. 
Only include items that would reasonably be within the possession, custody, or control of a {defendant_role} operating within a {facility}. Do not include irrelevant medical, financial, or third-party institutional records if they would not be held by this entity.

Format output as Word-style bullet points using asterisks (*).
Only return the list.

=== EXAMPLES ===
• Any and all highway-rail grade crossing incident reports, including initial accident reports, police or first responder reports submitted to the FRA, internal FRA documentation concerning the accident, and any witness statements or interviews conducted as part of the investigation;
• Any and all photographs, videos, surveillance footage, or imaging depicting the March 18, 2024 incident, or the truck or train involved in the collision immediately prior to, during, or immediately following the incident;
• Any and all correspondence, filings, emails, call logs, call recordings, complaints or other documents regarding the safety of or hazards imposed by the railroad crossing from 1990 to present;
• Any and all track inspection history for the segment of track at or near the railroad crossing, including routine and special inspection reports, records of deficiencies found during inspections, correspondence regarding any required or recommended repairs, and work orders or maintenance logs indicating repairs, modifications, or upgrades;
• Any and all safety audits of the crossing, including risk assessments conducted by the FRA; evaluations of crossing visibility, signaling, and warning devices; reports analyzing compliance with federal, state, or local safety regulations; and recommendations for safety improvements made by the FRA;
• Any and all complaints and prior accident reports associated with the railroad crossing, including complaints from the public, local government agencies, or railroad employees regarding the crossing's safety; reports of previous train-vehicle or train-pedestrian collisions at the location; and documentation of near-miss incidents or operational concerns;
• Any and all communication records related to the safety of the crossing before and after the March 18, 2024, accident, including emails, letters, or internal memoranda, as well as correspondence between the FRA and BNSF Railway, ODOT, or local authorities regarding maintenance, safety measures, or proposed improvements;
• Any and all data on train operations at the crossing, including records of train speeds and scheduled operations through the crossing, as well as any reports of delays or deviations from normal operations near the crossing on or around March 18, 2024;
• Any and all video footage or surveillance records, including any available locomotive event recorder (black box) data related to the accident and footage from onboard train cameras or nearby traffic cameras; and
• Any and all records, reports, correspondence, or other documentation concerning other motor vehicle accidents or injuries at the railroad crossing from 1990 to present.
Any and all maintenance logs for the railroad crossing, including records of inspections, repairs, modifications, or other maintenance activities conducted by or reported to ODOT;
• Any and all recommendations or evaluations relating to the railroad crossing, including internal assessments, third-party evaluations, proposed safety improvements, and engineering studies regarding the crossing’s condition or necessary upgrades;
• Any and all complaints or records of prior accidents at the railroad crossing, including reports submitted by the public, local government agencies, railroad personnel, or other stakeholders regarding safety concerns, near-misses, or previous collisions;
• Any and all records of ODOT’s involvement in response to this incident, including internal communications, coordination with law enforcement or emergency responders, and any actions taken following the March 18, 2024, accident;
• Any and all meeting minutes or records of discussions related to the safety of the railroad crossing, including agendas, notes, or transcripts from meetings involving ODOT, local officials, railroad representatives, or other relevant stakeholders;
• Any and all documents, reports, correspondence, or records concerning the inspection, maintenance, or safety improvements of the railroad crossing from 1990 to the present. This would encompass historical safety efforts, recommendations, and maintenance schedules;
• Records regarding any construction, maintenance, or safety improvements planned or implemented at the railroad crossing from 1990 to the present, including any planned upgrades or pending projects at the site to improve safety or functionality;
• Any and all records related to the communication between ODOT and third parties (including but not limited to BNSF Railway Company, local municipalities, or other agencies) concerning the safety, condition, or need for repair, maintenance, or other improvements to the railroad crossing; and
• Any and all documents or records concerning the jurisdictional responsibility of ODOT for maintaining the railroad crossing and any cross-agency discussions regarding safety protocols or enforcement of regulations at the crossing.
• Any and all reports related to this occurrence, (Case Number: 2024-0856);
• Any and all additional documents prepared in relation to this incident.
• Any and all NRFD reports documenting responses to incidents involving agents and/or employees of Hartgrove Hospital concerning a patient and/or minor during the time period from 1984 to the present.
• Any and all incident reports generated by the NRFD detailing responses to calls involving agents and/or employees of Hartgrove Hospital concerning a student and/or minor during the time period from 1984 to the present.
• Any and all recordings and/or transcripts of emergency calls (e.g., 911 calls) made to the NRFD or emergency services related to incidents involving agents and/or employees of Hartgrove Hospital concerning a patient and/or minor during the time period from 1984 to the present.
• Any and all communications, whether written or recorded, received by or sent from the NRFD, referencing incidents involving agents and/or employees of Hartgrove Hospital concerning a patient and/or minor during the time period from 1984 to the present.
• Copies of any and all statements, whether written or recorded, involving NRFD personnel or emergency responders in relation to investigations into incidents involving agents and/or employees of Hartgrove Hospital
Any and all BFS reports documenting responses to incidents involving agents and/or employees of Streamwood Hospital concerning a patient and/or minor during the time period from 1983 to the present.
• Any and all incident reports generated by the BFS detailing responses to calls involving agents and/or employees of Streamwood Hospital concerning a student and/or minor during the time period from 1983 to the present.
• Any and all recordings and/or transcripts of emergency calls (e.g., 911 calls) made to the BFS or emergency services related to incidents involving agents and/or employees of Streamwood Hospital concerning a patient and/or minor during the time period from 1983 to the present.
• Any and all communications, whether written or recorded, received by or sent from the BFS, referencing incidents involving agents and/or employees of Streamwood Hospital concerning a patient and/or minor during the time period from 1983 to the present.
• Copies of any and all statements, whether written or recorded, involving BFS personnel or emergency responders in relation to investigations into incidents involving agents and/or employees of Streamwood Hospital concerning a student and/or minor during the time period from 1983 to the present.
• Complete copies of any and all BFS investigative reports and/or files related to incidents involving a minor/student and agents and/or employees of Streamwood Hospital during the time period from 1983 to the present.
Only return the list.
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )
    return response.choices[0].message.content.strip()

# === OPENAI CALLS ===
def generate_bullet_points(case_synopsis, potential_requests, explicit_instructions, case_type, facility, defendant_role):
    prompt = build_prompt(case_synopsis, potential_requests, explicit_instructions, case_type, facility, defendant_role)
    return generate_with_openai(prompt).replace("* ", "")

def generate_synopsis(case_synopsis):
    prompt = f"""
Summarize the following legal case background in 2 professional sentences explaining what happened and the resulting harm or damages. Do not include any parties' names or personal identifiers:

{case_synopsis}
"""
    return generate_with_openai(prompt)

# === DOCX HELPER ===
def fill_template(context, template_path):
    doc = Document(template_path)
    for p in doc.paragraphs:
        for key, val in context.items():
            if f"{{{{{key}}}}}" in p.text:
                p.text = p.text.replace(f"{{{{{key}}}}}", val)
    return doc

# === MAIN FUNCTION ===
def run_foia(df):
    output_dir = "outputs/foias"
    template_path = "templates/foia_template.docx"
    os.makedirs(output_dir, exist_ok=True)
    output_paths = []

    for _, row in df.iterrows():
        try:
            context = {
                'client_id': str(row.get('Client ID', '')),
                'date': datetime.today().strftime("%B %d, %Y"),
                'defendant_name': row.get('Defendant Name', ''),
                'defendant_line1': row.get('Defendant Line 1 (address)', ''),
                'defendant_line2': row.get('Defendant Line 2 (City,state, zip)', ''),
                'doi': str(row.get('DOI', '')),
                'location': row.get('location of incident', ''),
                'synopsis': generate_synopsis(row.get('Case Synopsis', '')),
                'foia_request_bullet_points': generate_bullet_points(
                    row.get('Case Synopsis', ''),
                    row.get('Potential Requests', ''),
                    row.get('Explicit instructions', ''),
                    row.get('Case Type', ''),
                    row.get('Facility or System', ''),
                    row.get('Defendant Role', '')
                )
            }

            filename = f"FOIA_{context['client_id'].replace(' ', '_')}_{datetime.today().strftime('%Y-%m-%d')}.docx"
            output_path = os.path.join(output_dir, filename)
            doc = fill_template(context, template_path)
            doc.save(output_path)
            output_paths.append(output_path)
        except Exception as e:
            print(f"❌ Failed for {row.get('Client ID', '')}: {e}")
            continue

    return output_paths