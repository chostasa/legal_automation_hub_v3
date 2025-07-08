import os
import re
import time
from datetime import datetime
import streamlit as st
from docx import Document
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from openai import OpenAI, APIStatusError

try:
    api_key = st.secrets["OPENAI_API_KEY"]
except Exception:
    api_key = os.getenv("OPENAI_API_KEY", "")  # fallback for local dev

client = OpenAI(api_key=api_key)

def trim_to_token_limit(text, max_tokens=12000):
    if not text: return ""
    tokens = text.split()
    if len(tokens) <= max_tokens:
        return text
    third = max_tokens // 3
    return " ".join(tokens[:third]) + "\n...\n" + " ".join(tokens[-2 * third:])

def safe_generate(fn, *args, retries=3, wait_time=10, **kwargs):
    trimmed_args = [trim_to_token_limit(arg, 6000) if isinstance(arg, str) else arg for arg in args]
    for attempt in range(retries):
        try:
            return fn(*trimmed_args)
        except APIStatusError as e:
            if e.status_code == 429 and "rate_limit_exceeded" in str(e):
                st.warning(f"Rate limit hit. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("❌ gpt-3.5-turbo rate limit error after multiple attempts.")


def generate_with_openai(prompt, model="gpt-3.5-turbo"):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a professional legal writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()

def embed_quotes_in_section(text, quotes, heading="TESTIMONY"):
    """
    Append formatted quotes into a section body.
    """
    if not quotes.strip():
        return text.strip()

    return f"{text.strip()}\n\n{heading}:\n{quotes.strip()}"

def chunk_text(text, max_chars=6000):
    """
    Safely chunk long text inputs by character length to stay under GPT's context limit.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            # Avoid cutting off mid-sentence
            end = text.rfind(".", start, end) + 1 or end
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]

# === NEW FUNCTIONS FOR PREPROCESSING TRANSCRIPTS ===

def normalize_deposition_lines(raw_text):
    """
    Attaches the current page number to each line using format 0004:12.
    """
    lines = raw_text.splitlines()
    current_page = None
    numbered_lines = []

    for line in lines:
        page_match = re.match(r"^(0\d{3})\s*$", line.strip())
        if page_match:
            current_page = page_match.group(1)
            continue

        line_match = re.match(r"^\s*(\d{1,2})\s+(.*)$", line)
        if line_match and current_page:
            line_num = int(line_match.group(1))
            content = line_match.group(2).strip()
            full_id = f"{current_page}:{line_num:02d}"
            numbered_lines.append((full_id, content))

    return numbered_lines


def merge_multiline_qas(numbered_lines):
    """
    Rebuilds full Q/A blocks including multi-line content.
    Returns a string of the cleaned transcript.
    """
    qa_blocks = []
    buffer = []
    current_type = None

    for id_line, content in numbered_lines:
        if content.startswith("Q:"):
            if buffer:
                qa_blocks.append("\n".join(buffer))
                buffer = []
            current_type = "Q"
            buffer.append(f"{id_line} {content}")
        elif content.startswith("A:"):
            if buffer:
                qa_blocks.append("\n".join(buffer))
                buffer = []
            current_type = "A"
            buffer.append(f"{id_line} {content}")
        elif current_type in {"Q", "A"}:
            buffer.append(f"{id_line} {content}")

    if buffer:
        qa_blocks.append("\n".join(buffer))

    return "\n".join(qa_blocks)



# === Prompt Guidelines ===
NO_HALLUCINATION_NOTE = """
Do not fabricate or assume any facts. Use only what is provided. Avoid headings, greetings, and signoffs — the template handles those. Refer to the client by their first name only. Keep all naming, pronouns, and chronology consistent. Do not use more than one version of the incident. Do not repeat injury or treatment details across sections.
"""

LEGAL_FLUENCY_NOTE = """
Use the tone and clarity of a senior litigator. Frame facts persuasively using legal reasoning: duty, breach, causation, and harm. Eliminate redundancy, vague phrases, and casual storytelling. Frame liability clearly. Maintain formal, polished, and precise language. Quantify damages where possible. Refer to witnesses, police, and footage once. Avoid any instance of 'Jane Roe' or 'Amy' — only use the first name.
Do not restate the client’s injuries more than once. After the initial mention, refer to them only by category (e.g., “orthopedic trauma,” “soft tissue damage,” “ongoing symptoms”).

Eliminate any of the following weak or redundant phrases: “continues to uncover injuries,” “in the process of obtaining,” “we believe,” “potential footage,” or “may have been.”

Use strong, legally assertive alternatives:
- “Reports symptoms consistent with...”
- “Surveillance footage is being secured...”
- “Liability is well-supported by the available evidence...”

In the closing paragraph, avoid overexplaining. End firmly with one or two sentences:
“We invite resolution of this matter without the need for litigation. Should you fail to respond by [date], we are prepared to proceed accordingly.”

All content must sound like it was drafted for final review by a managing partner or trial attorney. Every sentence should advance legal theory, factual support, or damage justification — never simply restate.

Avoid summarizing facts multiple times. Focus instead on drawing conclusions from the established facts.
"""

BAN_PHRASING_NOTE = """
Ban any phrasing that introduces speculation or weakens factual strength. Do not use: “may,” “might,” “potential,” “appears to,” “possibly,” or “believes that.” Replace all with direct phrasing: “Jane is,” “The evidence will show,” “The footage depicts...”
"""

FORBIDDEN_PHRASES = """
Forbidden: “continues to discover injuries,” “a host of,” “significant emotional hardship,” “cannot be overlooked,” “it is clear that,” “ongoing discomfort,” “found herself,” “left her with,” “had to,” “was forced to,” “Jane was returning,” “she elected to,” “engrossed in conversation,” “was caught off guard”
"""

NO_PASSIVE_LANGUAGE_NOTE = """
Every sentence must use active voice. Eliminate all passive constructions. Do not say “was struck” or “has been advised.” Instead: “The snowplow struck Jane,” or “Jane is gathering...”
"""

INTRO_EXAMPLE = """
{{Plaintiff}} was performing his duties as a commercial truck driver in the early morning of April 1, 2022 when, while lawfully driving within the lane and within the speed limit, his tire caught an unmarked manmade pothole which protruded over the center dashline into the lane of travel. (Ex. A, Plaintiffs’ Complaint at Law). This manmade pothole was created and controlled by Defendants Keeley & Sons, Inc.; The Kilian Corporation; Kilian Transport, Inc.; and Asphalt Sales & Products, Inc.1 
Evidence will show, through video evidence from Plaintiff Zhu’s dash camera, the testimony of an eyewitness who watched Plaintiff Zhu’s driving for approximately 20 miles leading up to the crash, the conflicting testimony between the Defendants regarding their traffic control policies, and the testimony of the employee who was tasked with traffic control, that the Defendants acted with a conscious disregard for the safety of drivers passing through the construction zone. 
[BRIEF STATEMENT ABOUT MEDICALS]. 
The Killian Defendants have disclosed that they maintain an underlying insurance policy with applicable limits of $2,000,000.00 per occurrence and an excess policy with applicable limits of $10,000,000.00 ($12,000,000.00 total) covering the Subject Incident and all claims brought because of it.  Additionally, the Keeley & Sons Defendants have disclosed an underlying insurance policy with applicable limits of $1,000,000.00 per occurrence and an excess policy with applicable limits of $10,000,000.00 ($11,000,000.00) covering the Subject Incident and all claims brought because of it. Potential exceeds $23,000,000.00 for a case that has life altering injuries and punitive damages.  

"""


def generate_introduction(input_text, client_name):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}
{BAN_PHRASING_NOTE}
{FORBIDDEN_PHRASES}
{NO_PASSIVE_LANGUAGE_NOTE}

Use the following example as a style guide only. DO NOT copy content or facts.

Example:
{INTRO_EXAMPLE}

Now write the Introduction section of a confidential mediation memorandum for {client_name}. Focus on tone, structure, and legal fluency. Use only the information provided below:

{input_text}
"""
    return generate_with_openai(prompt)
# === Mediation Memo Section Generators ===


PLAINTIFF_STATEMENT_EXAMPLE = """
Plaintiff, Yafeng Zhu  
On April 1, 2022, Yafeng Zhu was driving a commercial truck in the left lane of Interstate 70 in Bond County, as the right lane was closed for construction, when his vehicle suddenly ripped off of the road, flipped over, and crashed into the tree line. Upon review, it was determined that the accident was caused by an unmarked open patch, which protruded across the center dashline and into the lane of travel. Mr. Zhu sustained life altering injuries to his neck and back. [ADDITIONAL DETAIL RE. INJURIES]. As a result of these injuries, he has undergone a variety of treatment, including, but not limited to physical therapy, injections, chiropractic treatment, electrical shock therapy, and prescription pain medication.  
At the time of collision, Mr. Zhu worked as a licensed commercial truck driver. (Ex. B, Zhu Dep. 9). He had been driving commercially for three years since receiving his commercial driver’s license in 2019 (Ex. B, Zhu Dep. 11). Since the day of the crash, Mr. Zhu has been unable to work as a commercial truck driver. (Ex. B, Zhu Dep. 46). Mr. Zhu continues to be treated for neck and back pain. He will continue to require physical therapy, pain medication, and injections.  
Plaintiff, Shuhui Zhang 
Shuhui Zhang, age 53, is the wife of Plaintiff Yafeng Zhu. Until the date of the incident, Mrs. Zhang relied on Mr. Zhu for income. (Ex. C, Zhang Dep. 7). Due to Mr. Zhu’s inability to work, Ms. Zhang has suffered a substantial loss in income in the household. Further, Mr. Zhu has not been able to contribute to the household in other non-income related ways, including cooking, cleaning, and a general decrease in his ability to provide love and caring for his family.  This has caused further stress on Mr. Zhu and Ms. Zhangs children, as they also relied on Mr. Zhu for financial support and assistance, and now have to work will attending school to ensure that they can afford the cost of living. 

"""


def generate_plaintiff_statement(bio, client_name):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Using only the info below, write a brief formal background on the Plaintiff ({client_name}):
{PLAINTIFF_STATEMENT_EXAMPLE}

Bio:
{bio}
"""
    return generate_with_openai(prompt)


DEFENDANT_STATEMENT_EXAMPLE = """

On April 1, 2022, Keeley & Sons, Inc, was a road construction and highway rehabilitation company overseeing a project at Milepost 37.6 on Interstate 70 in Bond County, Illinois as a sub-contractor. Keeley had been responsible for maintaining control of the worksite portion of the interstate during the project. Until the date of the incident, Keeley & Son’s had been in charge of the digging. [James Killian Dep] 
At all relevant times, Keeley had a duty to take any necessary actions to prevent any person or persons such as Plaintiffs, from being harmed by all manmade excavations, trenches, or cutouts near the worksite. Additionally, Keeley had a duty to ensure that traffic could flow through the worksite in a safe and practical manner or close the road to traffic entirely. As part of the project, Keeley oversaw the cut out in the roadway which had protruded into both lanes of traffic. [James Killian Dep] Keeley staffed multiple employees on this project both on-site and in managerial capacity. [CITE] Aaron Neuf was the Superintendent for this particular project. and was aware of Keeley’s policies and procedures. [CITE] Kevin Roeche was the General Superintendent, and he was also aware Keeley’s policies and procedures, and additionally had knowledge of why the cut out may have protruded into the left lane of traffic. [CITE] Tanner Thebeau, the president of Keeley & Son’s at the time of the incident, further acknowledged the dangers of the cut-out protruding into the left lane. [TANNER THEBEAU DEP] Additionally, Michael Lant was responsible for inspecting the site every in the evenings, and ensuring that safety barrels had been properly placed to indicate the existence of construction. [LANT DEP]  The safety of the work-site had been under the purview of Zachary Maggio. [MAGGIO DEP]  In his role at Keeley, Maggio’s duties included training employees emergency action plans and maintaining inspections of the site. [MAGGIO] 
The cut out in the roadway was not adequately marked so as to warn vehicles on the roadway of its protrusion into traffic, and a severe accident occurred as a result. Through multiple depositions of Keeley and Son’s associates, the common theme seems to be that of which, when shown footage of the worksite at the time of the incident, the cut out does not protrude into the traffic lane and the barrels are in proper form. All the while, other drivers on the road maintain the lack of fault on behalf of Plaintiffs. [MICHAEL DUNN] 
The Keeley defendants are seemingly unwilling, even after reviewing accident footage, to admit any fault, at the very least acknowledge that barrel placement may be inadequate, and when asked to place themselves in the shoes of Plaintiff, brush off the question as mere hypotheticals. [MAGGIO DEP] On other occasions, they maintain that there is nothing negligent regarding their placement. [MAGGIO DEP] 
The footage is clear, the cutout in the road protrudes into the traffic lane, and yet, even when reviewing the footage, some of Keeley Defendants deny the existence of such. It is this cut out in the road that, coupled with Keeley’s negligent handling of the construction site resulted in Plaintiff injuries.  
There remain multiple inconsistencies in Keeley Defendant statements, each varies either asserting that the safety barrels were in the right place, or that “wind” caused them to shift over, or that there was no safety issue in the first place. 

"""


def generate_defendant_statement(def_text, label="Defendant"):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write a detailed “Role” section for {label}.  
Describe who {label} is, their official role, what they were responsible for, and their relationship to the case.  
Use only the information below. Do not repeat facts from other sections.  
Match the professional tone and style of the example.

Example:
{DEFENDANT_STATEMENT_EXAMPLE}

Input:
{def_text}
"""
    return generate_with_openai(prompt)


DEMAND_EXAMPLE = """
The Killian Defendants have disclosed that they maintain an underlying insurance policy with applicable limits of $2,000,000.00 per occurrence and an excess policy with applicable limits of $10,000,000.00 ($12,000,000.00 total) covering the Subject Incident and all claims brought because of it.  Additionally, the Keeley & Sons Defendants have disclosed an underlying insurance policy with applicable limits of $1,000,000.00 per occurrence and an excess policy with applicable limits of $10,000,000.00 ($11,000,000.00) covering the Subject Incident and all claims brought because of it.  The policies for both the Killian Defendants and Keeley & Sons Defendants are underwritten by the same insurer, The Cincinnati Insurance Company.  This means the total applicable insurance coverage between these two Defendants that is potentially available to resolve all claims arising out of the Subject Incident is $23,000,000.00. (Ex. _, CERTIFICATES).  
"""

def generate_demand_section(summary, client_name):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}
{BAN_PHRASING_NOTE}
{FORBIDDEN_PHRASES}
{NO_PASSIVE_LANGUAGE_NOTE}

Write a mediation demand **paragraph** using the tone and clarity of the example below. 
This should be professional and persuasive—not a letter. Do not address “Dear Counsel” or sign off. This should simply be a summary.  

Example:
{DEMAND_EXAMPLE}

Facts:
{summary}
"""
    return generate_with_openai(prompt)



FACTS_LIABILITY_EXAMPLE = """
In the early morning of April 1, 2022, Yafeng Zhu was operating a commercial semi-tractor trailer westbound on I-70 in Bond County near the 38-mile mark (Ex. __, IDOT Highway Incident Report). According to an eyewitness who observed Mr. Zhu’s driving for about 20 miles and observed the accident, it was a dark morning, around 1:00am, and the area where the incident occurred was not lit. (Ex.__, Drum Dep. 69, 85). Around the area of the 38-mile mark, there was a construction zone containing several open patches. After lowering his speed, and staying within his own lane, Mr. Zhu’s right tire caught the edge of one of these open patches, which protruded into the left lane, which was the active lane of travel. The 90-degree drop-off in the open patch, which was about 8 to 10 inches over the center divider and 18 to 20 inches deep, caused Mr. Zhu’s truck to be ripped off the highway and into the tree line at an approximately 45-degree angle. (Ex.__, Drum Dep. 14, 24-26). As seen below, the barrel closest to the lane of travel left a substantial amount of this open patch unmarked.  
 
Image 1: Screenshot of Plaintiff Zhu’s Dashcam showing open Patch Protruding into left lane.2 
 
 
 
Image 2: Alternative Angle of Open Patch Protruding into left lane. 
 
Image 3: View of patch after completion, sourced by Google Maps in July 2022. 
Counsel for all parties to this case completed over 20 depositions. Throughout these depositions, agents for the Defendants gave conflicting testimony as to: the appropriateness of the barrel placement; whether the patch actually protruded into the left lane; what may have caused the barrel to be placed where it was; and how frequently the construction zone should have been observed after construction ended each day. 
A.	Appropriateness of Barrel Placement. 
a.	Keeley & Sons, Inc. 
Zachary Maggio, Safety Director for Keeley & Sons, Inc., believed that the barrel, as seen in Image 1, was appropriately placed. (Ex. __, Maggio Dep. 52). Aaron Neuf, Superintendent for Keeley & Sons, Inc., believed that the barrel was inappropriately located. (Ex.__, Neuf Dep. 107). Kevin Roeche, General Superintendent for Keeley & Sons, Inc., believed that the barrel was inappropriately placed. (Ex.___, Roeche Dep. 28-60). Tanner Thebeau, a former Project Manager and the current President of Keeley & Sons, Inc., stated that he does not believe the barrel would need to be corrected. (Ex. __, Thebeau Dep. 31). Lastly, Michael Lant, a Laborer for Keeley & Sons, Inc. who was specifically tasked with reviewing the placement of all traffic control devices at night believed that the barrel was appropriately placed and was consistently placed at the time of the accident with how he left the worksite. (Ex. __, Lant Dep. 60-61). 
b.	Kilian Defendants 
Steve Williams, the Operations Manager for The Kilian Corporation at the time of the incident, was of the impression after viewing the video of the incident that the barrels were appropriately placed. (Ex. __, Williams Dep. 48). Mr. Williams further stated that Joe Green, the General Foreman for The Kilian Corporation at the time of the incident, would also be considered the “Superintendent” for the project at the time of the incident. (Ex. __, Williams Dep. 41). Pursuant to The Kilian Corporation’s “Safety Health, and Loss Control Plan,” “The Superintendent shall be responsible for orderly traffic control on the job site and on any public roads affected by the work.”  (Ex. __, Kilian Corp. Safety Plan, 16). Mr. Green further affirmed that he had the authority to move barrels into the appropriate positions if he noticed them out of place. (Ex. __, Green Dep. 43). Mr. Green further stated that he would have positioned the barrels differently, towards the outermost edge of the open patch. (Ex. __, Green Dep. 47).  
c.	Other Witnesses 
Each of the responding officers who were on the scene provided testimony that there was sufficient space where the open patch had extended into the lane of travel for a tire of a vehicle that is lawfully within the lane of travel to catch on the open patch. Responding Officer Charis Hobbs stated that, had she seen the barrels placed where they were at the time of the incident, she would have called IDOT to have the contractor position them appropriately on the leading edge of the open patch. (Ex.___, Hobbs Dep. 12-13). She further stated that she believed a driver could be lawfully driving in the open lane of travel and get caught in the open patch. Id. Responding Officer Jacob Dorris further also shared the belief that the space to the left of the barrel and center line was sufficient for a truck tire to get caught in. (Ex.___, Dorris Dep. 40). Responding Officer Scott Becker also agreed that there was sufficient space within the lane of travel, unmarked by a barrier, for a tire to catch the open patch. 
Brent Winters, an Illinois Department of Transportation (“IDOT”) Engineer III, provided further statements as to the appropriateness of the barrel placement per IDOT specifications. Mr. Winters confirmed that the barrel placement was not proper according to IDOT standards. (Ex.___, Winters Dep. 38-39). 

"""


def generate_party_section(party_details):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write a “Parties” section using only the information below. Describe the Plaintiff and all Defendants, including any employer or corporate affiliations. Keep it factual, professional, and concise.

Example:
{PLAINTIFF_STATEMENT_EXAMPLE}

Input:
{party_details}
"""
    return generate_with_openai(prompt)

def generate_party_summary(plaintiff_names, defendant_names):
    """
    Generates a one-paragraph narrative describing all plaintiffs and all defendants.
    """
    plaintiff_list = ", ".join(plaintiff_names)
    defendant_list = ", ".join(defendant_names)

    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write a single narrative paragraph describing all parties to the action.
Include each Plaintiff’s name, role, and jurisdictional detail. Do the same for all Defendants.
Use only this list:

Plaintiffs: {plaintiff_list}
Defendants: {defendant_list}

Keep it factual, formal, and brief — like the first paragraph of a complaint. Do not summarize allegations or damages here.
"""
    return generate_with_openai(prompt)


def generate_facts_liability_section(facts, deposition_text=None):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Draft the Facts / Liability section using only this information:
{facts}
"""
    if deposition_text:
        prompt += f"""
You may reference **direct quotes** from the following deposition excerpts if they support liability. Introduce them professionally (e.g., \"As {{plaintiff}} testified, ...\" or \"Deposition excerpts confirm...\"):

Deposition excerpts for liability:
{deposition_text}
"""

    prompt += f"\n\nExample:\n{FACTS_LIABILITY_EXAMPLE}"
    return generate_with_openai(prompt)

CAUSATION_EXAMPLE = """
As a result of this occurrence, Stan will require a decompressive hemilaminectomy and microdiscectomy at L5-S1.
On August 8, 2018, Mr. {{Plaintiff}} was a restrained driver of a semi-tractor trailer stopped in traffic and rear-ended by another semi truck. On August 9, 2018 Mr. Doe saw Dr. Jaroslav Goldman at East West Internal Medicine Associates in Wheeling, IL to address pain he was experiencing as a result of the accident the day before. He complained of back pain, dizziness, fatigue, headaches, insomnia and neck pain. His assessment noted an acceleration-deceleration injury of the neck, muscle spasms and external constriction of the neck. He was prescribed to begin physical therapy, chiropractic manipulations and X-rays of the lumbosacral spine. (Ex. G, Doe Medical Records).

Mr. Doe began chiropractic treatment with Dr. Kaspars Vilems, DC on August 10, 2018. The treatment plan was intended to address Mr. Efimov’s pain in his neck and upper and lower back. Dr. Vilems performed a series of chiropractic manipulations, electric stimulations, and therapeutic exercises at each appointment (Ex. G, Doe Medical Records). Mr. Doe continued this therapy until October 19, 2018. At that point he had attended 21 chiropractic therapy visits.
On August 28, 2018, Mr. Doe underwent an MRI of the lumbar spine ordered by Dr. Vilems for his low back pain. The MRI revealed a high-density zone in the left lateral fibers of the L4-5 disc suggestive of an annular tear.
On October 4, 2018, Mr. Doe had a pain consultation with Dr. Yuriy Bukhalo at Northwest Suburban Pain Center for his bilateral low back pain radiating to his right knee. Mr. Doe reported that he began feeling pain after sitting for more than 15 minutes, making it difficult to continue working as a truck driver. Dr. Bukhalo agreed that the annular tear detected in the lumbar spine MRI was likely the cause of this pain and recommended intensifying physical therapy, wearing a brace, and initiating an anti-inflammatory.
At a follow-up appointment on October 23, Dr. Bukhalo performed right L4-5 and L5-S1 transforaminal epidural steroid injections (TFESIs). At the next appointment on November 6, Mr. Doe reported 60% ongoing pain improvement. He still felt pain while sitting for long periods of time. Due to this pain, he was forced to change his job as a truck driver to a managerial position with the trucking company he drove for (Ex. A, Doe Dep. 67). Dr. Bukhalo performed the same TFESIs at this appointment (Ex. G, Doe Medical Records).

By November 12, 2019, Mr. Efimov’s lower back pain had not subsided. He had a surgical consultation with Dr. Sean Salehi at the Neurological Surgery & Spine Surgery S.C. to address his continuing low back pain. Dr. Salehi found that Mr. Doe was not a surgical candidate due to his elevated BMI and intermittent symptoms and was referred to pain management instead.
Mr. Doe scheduled an appointment for December 4, 2019, with Dr. Krishna Chunduri at Advanced Spine and Pain Specialists for his lower back pain. He was prescribed a Medrol Dosepak for his pain flare-ups.
On March 17, 2020, he had a visit with Dr. Mark Farag at Midwest Anesthesia and Pain Specialists. Mr. Doe reported that the injections performed by Dr. Bukhalo took the pain away for approximately three to four months. The assessment noted low back pain, lumbar radiculopathy, lumbar intervertebral disc displacement, and lumbosacral spondylosis with myelopathy or radiculopathy. Dr. Farag recommended an L5-S1 lumbar epidural steroid injection (LESI).
Mr. Doe followed up with Dr. Farag on January 26, 2021. He reported worsening back pain with intermittent numbness and tingling in the right lower extremity. At this point, he had completed physical therapy and was participating in a home exercise program. Dr. Farag once again recommended an L5-S1 LESI. This injection was performed on February 18, 2021.
On March 4, 2021, Mr. Doe reported to Dr. Farag that he had an improvement in pain since his injection, but still felt intermittent radiating pain in his right leg. Dr. Farag ordered right L4-L5 and L5-S1 TFESIs. These injections were performed on May 27, 2021.
His most recent MRI occurred on June 20, 2022 at Empire Imaging in Pembroke Pines, FL. This scan found a disc bulge with a superimposed right foraminal disc herniation at L3-4 and a disc bulge with a left foraminal disc herniation at L4-5. At L5-S1 there is a disc bulge with superimposed right posterior disc herniation.
At present, Mr. Doe reports that his conditions remain symptomatic and cause ongoing disability including sciatic nerve pain. He reports that his low back and lower extremity pain remains present despite undergoing extensive therapy.

"""
def generate_causation_injuries(causation_info):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write a paragraph connecting the incident to the client’s injuries and medical course.

Example:
{CAUSATION_EXAMPLE}

Facts:
{causation_info}
"""
    return generate_with_openai(prompt)


HARMS_EXAMPLE = """
Prior to this collision, Mr. Doe was a healthy and active 38-year-old man who enjoyed playing basketball, tennis, and soccer at the park with his friends (Ex. A, Doe Dep. 77). 
Since the day of the crash, Stan has not been able to drive a truck.  He physically cannot climb into a truck, sit for long hours, work to unhitch the trailer, and climb out of the truck.  He enjoyed playing with and lifting up his niece, who weighs 25 pounds (Ex. A, Doe Dep. 79). Since the accident, he has been unable to partake in these activities that once brought him great joy. Mr. Doe had been driving commercial trucks since 2014 and was forced to step away from driving because of the intense pain he experienced after sitting for prolonged periods of time (Ex. A, Doe Dep. 67). As a result of the collision and to this date, he has been unable to do any these activities without experiencing severe, debilitating pain and has, therefore, lost the quality of life he once had. He had no previous neck or back injuries before this accident.
"""
FUTURE_BILLS_EXAMPLE = """
Mr. Doe’s ongoing symptoms will require lifelong pain management. Based on his treating providers’ evaluations and the history of pain persistence despite conservative treatment, Plaintiff is expected to undergo future interventions such as repeat TFESI injections and potentially spinal surgery. The cost of these procedures, including follow-up physical therapy, imaging, and medication, is estimated to exceed $150,000 over his lifetime.
"""

def generate_additional_harms(harm_info, deposition_text=None):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write the “Additional Harms and Losses” section based on the information below.

Input:
{harm_info}
"""
    if deposition_text:
        prompt += f"""

You may quote directly from the following deposition excerpts to reinforce impact on daily life, work, or emotional well-being:

Deposition excerpts for damages:
{deposition_text}
"""

    prompt += f"\n\nExample:\n{HARMS_EXAMPLE}"
    return generate_with_openai(prompt)


def generate_future_medical(future_info, deposition_text=None):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Draft a future medical expenses section using this tone:

{FUTURE_BILLS_EXAMPLE}

Input:
{future_info}
"""
    if deposition_text:
        prompt += f"""

You may quote directly from the following deposition excerpts to reinforce impact on daily life, work, or emotional well-being:

Deposition excerpts for damages:
{deposition_text}
"""
    return generate_with_openai(prompt)


CONCLUSION_EXAMPLE = """
Plaintiff’s past and future medical bills alone nearly exceed the purported $1 million dollar 
policy that STL Truckers has for their and their Driver’s punitive actions causing Stan life altering injuries and damages. Stan, now 42, has 30 plus years of pain, suffering, and loss of normal life related to this occurrence caused by STL Truckers putting a trucker on the road who was not trained for the job.
"""


def generate_conclusion_section(notes):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write the closing section of a mediation memo.

Example:
{CONCLUSION_EXAMPLE}

Input:
{notes}
"""
    return generate_with_openai(prompt)


# === Improved Placeholder Replacer ===
def replace_placeholders(doc, replacements):
    def rebuild_paragraph(paragraph):
        combined_text = "".join(run.text for run in paragraph.runs)
        for key, val in replacements.items():
            combined_text = combined_text.replace(key, val)
        if combined_text.strip():  # Only replace if there's something to write
            # Clear and reset
            for run in paragraph.runs:
                run.text = ""

            if paragraph.runs:
                paragraph.runs[0].text = combined_text
            else:
                paragraph.add_run(combined_text)


            if not paragraph.runs:
                paragraph.add_run()

    def replace_in_cell(cell: _Cell):
        for paragraph in cell.paragraphs:
            rebuild_paragraph(paragraph)

    for paragraph in doc.paragraphs:
        rebuild_paragraph(paragraph)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                replace_in_cell(cell)

# === Template Filler ===

def fill_mediation_template(data, template_path, output_path):
    from docx import Document
    import os
    from datetime import datetime

    doc = Document(template_path)

    # Start with updated static placeholders
    replacements = {
        "{{Court}}": data.get("court", ""),
        "{{Case_Number}}": data.get("case_number", ""),
        "{{Introduction}}": data.get("introduction", ""),
        "{{Parties}}": data.get("parties", ""),
        "{{Demand}}": data.get("demand", ""),
        "{{Facts_Liability}}": data.get("facts_liability", ""),
        "{{Causation_Injuries_Treatment}}": data.get("causation_injuries", ""),
        "{{Additional_Harms_Losses}}": data.get("additional_harms", ""),
        "{{Future_Medical_Bills}}": data.get("future_bills", ""),
        "{{Conclusion}}": data.get("conclusion", ""),
        "{{Plaintiff_1_Name}}": data.get("plaintiff1", ""),
        "{{Plaintiff_1_Statement}}": data.get("plaintiff1_statement", ""),
        "{{Plaintiff_2_Name}}": data.get("plaintiff2", ""),
        "{{Plaintiff_2_Statement}}": data.get("plaintiff2_statement", ""),
        "{{Plaintiff_3_Name}}": data.get("plaintiff3", ""),
        "{{Plaintiff_3_Statement}}": data.get("plaintiff3_statement", ""),
        "{{Defendant_1_Name}}": data.get("defendant1", ""),
        "{{Defendant_1_Statement}}": data.get("defendant1_statement", ""),
        "{{Defendant_2_Name}}": data.get("defendant2", ""),
        "{{Defendant_2_Statement}}": data.get("defendant2_statement", ""),
        "{{Defendant_3_Name}}": data.get("defendant3", ""),
        "{{Defendant_3_Statement}}": data.get("defendant3_statement", ""),
        "{{Defendant_4_Name}}": data.get("defendant4", ""),
        "{{Defendant_4_Statement}}": data.get("defendant4_statement", ""),
        "{{Defendant_5_Name}}": data.get("defendant5", ""),
        "{{Defendant_5_Statement}}": data.get("defendant5_statement", ""),
        "{{Defendant_6_Name}}": data.get("defendant6", ""),
        "{{Defendant_6_Statement}}": data.get("defendant6_statement", ""),
        "{{Defendant_7_Name}}": data.get("defendant7", ""),
        "{{Defendant_7_Statement}}": data.get("defendant7_statement", ""),
    }

    def rebuild_paragraph(paragraph):
        original_text = "".join(run.text for run in paragraph.runs)
        replaced_text = original_text
        for key, val in replacements.items():
            replaced_text = replaced_text.replace(key, val)

        if replaced_text != original_text:
            for run in paragraph.runs:
                run.text = ""
            if paragraph.runs:
                paragraph.runs[0].text = replaced_text
            else:
                paragraph.add_run(replaced_text)

    def replace_in_cell(cell):
        for paragraph in cell.paragraphs:
            rebuild_paragraph(paragraph)

    for paragraph in doc.paragraphs:
        rebuild_paragraph(paragraph)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                replace_in_cell(cell)

    plaintiff_name = data.get("plaintiff", "Unknown").replace(" ", "_")
    filename = f"Mediation_Memo_{plaintiff_name}_{datetime.today().strftime('%Y-%m-%d')}.docx"
    output_file_path = os.path.join(output_path, filename)
    print("📄 Placeholder values used in template:")
    for k, v in replacements.items():
        print(f"{k}: {'[FILLED]' if v else '[EMPTY]'}")
    doc.save(output_file_path)

    return output_file_path


# --- Safe wrapper to handle OpenAI rate limits ---

import re

def redact_text(text):
    """
    Redacts sensitive info (PHI) from already OCR'd or typed text.
    """
    text = re.sub(
        r"\b(?:DOB|D\.O\.B)\s*[:\-]?\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}", "[REDACTED DOB]", text, flags=re.I
    )
    text = re.sub(
        r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED SSN]", text
    )
    text = re.sub(
        r"\b(Name|Patient)\s*[:\-]?\s*[A-Z][a-z]+\s[A-Z][a-z]+", "[REDACTED NAME]", text
    )
    return text

# --- Main time split function ---
def generate_quotes_in_chunks(text_chunks, depo_label="Dep.", delay_seconds=10, custom_instructions=""):
    """
    Categorize Q&A deposition quotes by Liability and Damages.
    Appends (Ex. A, [Deposition Label] [Page#]) to each Q/A block.
    """
    liability_quotes = []
    damages_quotes = []

    for i, chunk in enumerate(text_chunks):
        sub_chunks = chunk_text(chunk, max_chars=6000)

        for j, sub_chunk in enumerate(sub_chunks):
            prompt = f"""
You are a litigation analyst reviewing deposition excerpts.

{custom_instructions.strip() if custom_instructions else "Categorize all Q&A pairs into **Liability** or **Damages** only."}

🧾 **Return Format (strict)**:
Only include bullet points like this:
- **0012:25 Q:** "What were you responsible for on that day?"  
  **0012:26 A:** "I was supervising the road closure."

📂 **Categories**:
**Liability** = Questions or answers about duties, fault, conduct, knowledge of events, observations, or cause of the incident.  
**Damages** = Anything about pain, treatment, limitations, daily impact, job loss, suffering, or future care.

⚠️ **Rules**:
- Each bullet must include both the Q and A with proper line numbers.
- Quotes must be exact. No paraphrasing. No summaries. No interpretation.
- Use quotation marks. Do not reformat Qs or As.
- If a line is cut off, include only the first full line.
- No duplicates. Do not repeat quotes across categories or chunks.

📄 **Excerpt**:
{sub_chunk}

"""
            try:
                result = safe_generate(generate_with_openai, prompt)

                # Parse out the quotes
                liability_section = re.findall(r"\*\*Liability\*\*(.*?)(?=\*\*Damages\*\*|$)", result, re.DOTALL)
                damages_section = re.findall(r"\*\*Damages\*\*(.*)", result, re.DOTALL)

                if liability_section:
                    liability_quotes.append(liability_section[0].strip())
                if damages_section:
                    damages_quotes.append(damages_section[0].strip())

                print(f"Processed chunk {i+1}.{j+1}/{len(text_chunks)}")
            except APIStatusError as e:
                print(f"API error on chunk {i+1}.{j+1}: {e}")
                raise e

            if j < len(sub_chunks) - 1:
                time.sleep(delay_seconds)

    def clean_and_dedup(quotes):
        combined = "\n".join(quotes)
        seen = set()
        cleaned = []
        for line in combined.splitlines():
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                cleaned.append(line)
        return "\n".join(cleaned)

    def format_quotes_with_label(quotes_text, depo_label):
        """
        Appends (Ex. A, [Deposition Label] [Page#]) to each Q/A pair using the line number.
        """
        output = []
        for block in quotes_text.strip().split("\n"):
            match = re.search(r"\*\*(\d{4}):(\d{2}) Q:\*\*", block)
            if match:
                page = match.group(1).lstrip("0")
                citation = f"(Ex. A, {depo_label} {page})"
                output.append(f"{block} {citation}")
            else:
                output.append(block)
        return "\n".join(output)

    return {
        "liability_quotes": format_quotes_with_label(clean_and_dedup(liability_quotes), depo_label),
        "damages_quotes": format_quotes_with_label(clean_and_dedup(damages_quotes), depo_label)
    }



def split_and_combine(fn, long_text, quotes="", chunk_size=3000):
    chunks = [long_text[i:i+chunk_size] for i in range(0, len(long_text), chunk_size)]
    results = []
    for chunk in chunks:
        if quotes:
            results.append(safe_generate(fn, chunk, quotes))
        else:
            results.append(safe_generate(fn, chunk))
    return "\n\n".join(results)
    # --- Main generation function ---

def polish_text_for_legal_memo(text):
    prompt = f"""
You are a senior legal editor. Improve the following legal writing by:
- Converting to active voice
- Eliminating redundant or vague phrases
- Removing repetition of facts already stated
- Keeping it formal, persuasive, and professionally polished
- Do not introduce new facts or change case theory

Text:
{text}
"""
    return safe_generate(generate_with_openai, prompt)

def generate_memo_from_summary(data, template_path, output_dir, text_chunks):
    import time
    memo_data = {}

    plaintiff_sections = []
    defendant_sections = []

    memo_data["Plaintiffs"] = ", ".join(
        [data.get(f"plaintiff{i}", "") for i in range(1, 4) if data.get(f"plaintiff{i}", "")]
    )
    memo_data["Defendants"] = ", ".join(
        [data.get(f"defendant{i}", "") for i in range(1, 8) if data.get(f"defendant{i}", "")]
    )

    memo_data["court"] = data["court"]
    memo_data["case_number"] = data["case_number"]

    # Determine primary plaintiff
    plaintiff1 = data.get("plaintiff1") or data.get("plaintiff") or "Plaintiff"
    memo_data["plaintiff"] = plaintiff1
    memo_data["plaintiff1"] = plaintiff1
    memo_data["plaintiff1_statement"] = safe_generate(
        generate_plaintiff_statement, trim_to_token_limit(data["complaint_narrative"], 4000), plaintiff1
    )
    time.sleep(20)
    plaintiff_sections.append(memo_data["plaintiff1_statement"])


    # Handle up to 3 plaintiffs
    for i in range(2, 4):
        name = data.get(f"plaintiff{i}", "").strip()
        if name:
            memo_data[f"plaintiff{i}"] = name
            statement = safe_generate(generate_plaintiff_statement, data["complaint_narrative"], name)
            memo_data[f"plaintiff{i}_statement"] = statement
            plaintiff_sections.append(statement)
            time.sleep(20)


    # Handle up to 7 defendants dynamically
    for i in range(1, 8):
        key = f"defendant{i}"
        name = data.get(key, "")
        memo_data[key] = name
        if name:
            statement = safe_generate(generate_defendant_statement, data["complaint_narrative"], name)
            memo_data[f"{key}_statement"] = statement
            defendant_sections.append(statement)
            time.sleep(20)
        else:
            memo_data[f"{key}_statement"] = ""


    # Main body content
    memo_data["introduction"] = polish_text_for_legal_memo(
        safe_generate(generate_introduction, trim_to_token_limit(data["complaint_narrative"], 4000), plaintiff1)
    )
    time.sleep(20)

    memo_data["demand"] = polish_text_for_legal_memo(
        safe_generate(generate_demand_section, trim_to_token_limit(data["settlement_summary"], 2000), plaintiff1)
    )
    time.sleep(20)

    quotes_dict = generate_quotes_in_chunks(text_chunks, delay_seconds=20)
    trimmed_medical_summary = trim_to_token_limit(data.get("medical_summary", ""), 10000)
    liability_quotes = quotes_dict["liability_quotes"]
    damages_quotes = quotes_dict["damages_quotes"]

    memo_data["facts_liability"] = polish_text_for_legal_memo(
        embed_quotes_in_section(
            "\n\n".join([
                safe_generate(generate_facts_liability_section, chunk, trim_to_token_limit(liability_quotes, 2000))
                for chunk in chunk_text(data["complaint_narrative"])
            ]),
            liability_quotes,
            heading="Liability Testimony"
        )
    )
    time.sleep(20)

    memo_data["additional_harms"] = polish_text_for_legal_memo(
        embed_quotes_in_section(
            "\n\n".join([
                safe_generate(generate_additional_harms, chunk, trim_to_token_limit(damages_quotes, 2000))
                for chunk in chunk_text(trimmed_medical_summary)
            ]),
            damages_quotes,
            heading="Damages Testimony"
        )
    )
    time.sleep(20)

    memo_data["future_bills"] = polish_text_for_legal_memo(
        "\n\n".join([
            safe_generate(generate_future_medical, chunk, trim_to_token_limit(damages_quotes, 2000))
            for chunk in chunk_text(trimmed_medical_summary)
        ])
    )
    time.sleep(20)

    memo_data["causation_injuries"] = polish_text_for_legal_memo(
        "\n\n".join([
            safe_generate(generate_causation_injuries, chunk)
            for chunk in chunk_text(trimmed_medical_summary)
        ])
    )
    time.sleep(20)

    # === Generate narrative and full parties section ===
    plaintiff_names = [memo_data.get(f"plaintiff{i}", "") for i in range(1, 4) if memo_data.get(f"plaintiff{i}", "")]
    defendant_names = [memo_data.get(f"defendant{i}", "") for i in range(1, 8) if memo_data.get(f"defendant{i}", "")]

    memo_data["parties"] = polish_text_for_legal_memo(
        safe_generate(generate_party_summary, plaintiff_names, defendant_names)
    )

    if plaintiff_sections:
        memo_data["parties"] += "\n\nPLAINTIFFS:\n" + "\n\n".join(plaintiff_sections) + "\n\n"
    if defendant_sections:
        memo_data["parties"] += "DEFENDANTS:\n" + "\n\n".join(defendant_sections)


    # === Final cleanup and formatting ===
    memo_data["conclusion"] = polish_text_for_legal_memo(
        safe_generate(generate_conclusion_section, data["settlement_summary"])
    )

    memo_data["Introduction"] = memo_data.pop("introduction", "")
    memo_data["Demand"] = memo_data.pop("demand", "")
    memo_data["Facts_Liability"] = memo_data.pop("facts_liability", "")
    memo_data["Causation_Injuries_Treatment"] = memo_data.pop("causation_injuries", "")
    memo_data["Additional_Harms_Losses"] = memo_data.pop("additional_harms", "")
    memo_data["Future_Medical_Bills"] = memo_data.pop("future_bills", "")
    memo_data["Conclusion"] = memo_data.pop("conclusion", "")

    for key in ["Introduction", "Facts_Liability", "Additional_Harms_Losses", "Future_Medical_Bills", "Conclusion"]:
        if memo_data.get(key):
            memo_data[key] = re.sub(r"\s{2,}", " ", memo_data[key].strip())

    for i in range(1, 4):
        memo_data[f"Plaintiff_{i}_Name"] = memo_data.get(f"plaintiff{i}", "")
        memo_data[f"Plaintiff_{i}_Statement"] = memo_data.get(f"plaintiff{i}_statement", "")

    for i in range(1, 8):
        memo_data[f"Defendant_{i}_Name"] = memo_data.get(f"defendant{i}", "")
        memo_data[f"Defendant_{i}_Statement"] = memo_data.get(f"defendant{i}_statement", "")

    file_path = fill_mediation_template(memo_data, template_path, output_dir)

    return file_path, memo_data

def generate_plaintext_memo(memo_data):
    """
    Fallback: Generate a plain text version of the memo from all memo_data.
    """
    sections = [
        ("Court", memo_data.get("court", "")),
        ("Case Number", memo_data.get("case_number", "")),
        ("Introduction", memo_data.get("introduction", "")),
        ("Parties", memo_data.get("parties", "")),
        ("Demand", memo_data.get("demand", "")),
        ("Facts / Liability", memo_data.get("facts_liability", "")),
        ("Causation, Injuries, and Treatment", memo_data.get("causation_injuries", "")),
        ("Additional Harms and Losses", memo_data.get("additional_harms", "")),
        ("Future Medical Bills", memo_data.get("future_bills", "")),
        ("Conclusion", memo_data.get("conclusion", ""))
    ]

    # Add plaintiff and defendant blocks
    for i in range(1, 4):
        name = memo_data.get(f"plaintiff{i}", "")
        statement = memo_data.get(f"plaintiff{i}_statement", "")
        if name or statement:
            sections.append((f"Plaintiff {i}: {name}", statement))

    for i in range(1, 8):
        name = memo_data.get(f"defendant{i}", "")
        statement = memo_data.get(f"defendant{i}_statement", "")
        if name or statement:
            sections.append((f"Defendant {i}: {name}", statement))

    # Build plain text
    lines = []
    for title, content in sections:
        if content.strip():
            lines.append(f"=== {title.upper()} ===\n{content.strip()}\n")

    return "\n".join(lines)

