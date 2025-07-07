from openai import APIStatusError
import time
import os
from datetime import datetime
from docx import Document
from docx.table import _Cell
from docx.text.paragraph import Paragraph
from openai import OpenAI
import streamlit as st

try:
    api_key = st.secrets["OPENAI_API_KEY"]
except Exception:
    api_key = os.getenv("OPENAI_API_KEY", "")  # fallback for local dev

client = OpenAI(api_key=api_key)


def generate_with_openai(prompt):
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "You are a professional legal writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    return response.choices[0].message.content.strip()


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
{{Plaintiff}}, 42, will require a L5-S1 decompressive hemilaminectomy and microdiscectomy as a result of the Defendant driver rear ending Stan at over 50 mph on his very first trip as a trucker. Plaintiff has been given leave to pursue punitive damages against the defendants. Defendant STL Trucking has failed to produce even one witness for deposition. STL claims that no STL personnel have knowledge of the crash and that depositions are not relevant. (Ex. A, Plaintiff’s Complaint at Law)
The jury will punish defendants and STL Truckers for their conscious disregard for safety and training of the Defendant driver. Mr. Doe has permanent disc herniations at L3-4, L4-5, and L5-S1. Plaintiff will require future medical care including surgery, injections and physical therapy for the rest of his life. Mr. Doe will require $869,952.41 related to the August 8, 2018 crash.
Defendants state they have a $1,000,000.00 eroding policy for this case.  They refuse to sign an affidavit that there is excess or umbrella coverage.  Plaintiff made a pre-suit demand of $1,000,000.00.  Defendants had offered a nominal amount of $50,000.00.  Stan will begin negotiating when Plaintiff is aware of the true policy limits. Verdict potential exceeds $3,000,000.00 for a case that has life altering injuries and punitive damages.
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
On August 8, 2018, {{Plaintiff}}, then 38, was driving a commercial truck in the right lane of I-65 when his vehicle was rear-ended at a speed exceeding 50mph. Mr. Doe sustained life altering injuries to his neck and back. Mr. Doe suffered disc herniations at L3-4, L4-5, and L5-S1.  These injuries resulted in fiber tears, disc bulges, nerve injuries, radiating pain, dizziness, and limited mobility.   As a result of these injuries, he has undergone a variety of treatment, including, but not limited to physical therapy, injections, chiropractic treatment, electrical shock therapy, and prescription pain medication.
At the time of collision, Mr. Doe worked as a licensed commercial truck driver. (Ex. B, Doe Dep. 68-69). He had been driving commercially for four years since receiving his commercial driver’s license in 2014 (Ex. B, Doe Dep. 15). He had purchased part of his commercial truck with the goal of eventually starting his own commercial trucking company (Ex. B, Doe Dep. 88). Since the day of the crash, Mr. Doe has been unable to work as a commercial truck driver. (Ex. B, Doe Dep. 66). He now works as a dispatcher. Mr. Doe continues to be treated for neck and back pain. He will continue to require physical therapy, pain medication, and injections.
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

On August 8, 2018, {{Defendant1}}, then 43, was driving a commercial truck for the first time in the right lane of I-65 when he ran through Mr. Efimov’s truck. The police who responded to the accident cited Defendant Rakhimdjanov with following too closely behind Mr. Doe (Ex. C, Indiana Crash Report). After colliding into Mr. Efimov, Mr. Rakhimdjanov veered into the left, crashing into another vehicle, which crashed into the vehicle in front of it, before coming to a stop in the left lane (Ex. D, Rakhimdjanov Dep. 53).
At the time of the collision, Mr. Rakhimdjanov had been driving commercially for less than one day.  This was his first commercial driving job (Ex. D, Rakhimdjanov Dep. 30). Mr. Rakhimdjanov used an interpreter when he gave his deposition on December 16, 2021 and when he signed his employment contracts with STL Truckers. (Ex. D, Rakhimdjanov Dep. 73). However, Mr. Rakhimdjanov did not have an interpreter during his training with STL Truckers. (Ex. D, Rakhimdjanov Dep. 73). It is clear from the documents from STL that he did not even write his own name.
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
STL Trucking has represented to Plaintiff’s counsel that they only have a $1 million policy available for Mr. Efimov’s losses. To date, STL has yet to sign an affidavit verifying coverage. (Ex. F, Affidavit of No Excess Coverage).
"""


def generate_demand_section(summary, client_name):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write the mediation demand for {client_name}. Use this example for tone and structure:

{DEMAND_EXAMPLE}

Summary of case:
{summary}
"""
    return generate_with_openai(prompt)


FACTS_LIABILITY_EXAMPLE = """
In the early afternoon of August 8, 2018, {{Plaintiff}} was operating a commercial semi-tractor trailer on I-65 near the 184-mile mark (Ex. C, Indiana Crash Report). It was a dry, sunny day, and Mr. Doe noted that first responders were at the site of a collision approximately one-quarter mile ahead (Ex. B, Doe Dep. 28-29). Traffic was at a complete stop (Ex. B, Doe Dep. 28). In accordance with his occupational training and four years of commercial truck driving experience, Mr. Doe slowly decelerated his vehicle and came to a stop two cars’ lengths—roughly 15 feet—behind the car in front of him (Ex. A, Doe Dep. 28, 35).
At the same time, defendant {{Defendant1}} was operating a commercial semi-tractor trailer for his first full day on the job. (Ex. D, Rakhimdjanov Dep. 35). Roughly 10 to 15 seconds after Mr. Doe had come to a complete stop, at approximately 1:45 PM, defendant violently crashed into the back of Mr. Efimov’s trailer (Ex. B, Doe Dep. 29). Defendant was traveling at a speed of about 60 to 65 miles per hour (Ex. C, Indiana Crash Report). The Defendant was traveling so fast at the time of collision that no tire marks were found at the scene.
Defendant driver’s truck knocked Stan’s truck off its frame.
The force of the collision caused Mr. Efimov’s head to violently snap forwards and backwards (Ex. A, Doe Dep. 86). Mr. Doe heard no warning sounds, no horns, and no break noises prior to the collision, and later found no skid marks on the road (Ex. A, Doe Dep. 39). In fact, defendant’s vehicle had so much momentum at the point of impact that defendant’s vehicle displaced Mr. Efimov’s commercial semi-tractor nearly 15 feet forward, causing the cab to come off its frame (Ex. A, Doe Dep. 41).
After making contact with Mr. Efimov’s truck, defendant veered into the left lane and collided with another vehicle (Ex. B, Indiana Crash Report). This vehicle was pushed forward, striking the vehicle in front of it, eventually coming to rest in the median (Ex. B, Indiana Crash Report). Three of the four vehicles involved in this incident had to be towed away (Ex. B, Indiana Crash Report). That day, Mr. Doe began experiencing neck pain, back pain, and dizziness (Ex. A, Doe Dep. 49). At his hotel in the morning, his pain was so extreme that he had to call his father to physically help him get out of bed, to go to the restroom, and to get into his car. He sought medical the next day back in Chicago (Ex. A, Doe Dep. 49).
"""
PARTIES_EXAMPLE = """
Plaintiff Stan Efimov is a resident of Cook County, Illinois. Defendant STL Truckers is a commercial carrier incorporated in Indiana, conducting business in Illinois, and was the employer of Defendant driver Arsen Rakhimdjanov. Defendant Arsen Rakhimdjanov was operating a commercial truck within the scope of his employment with STL Truckers at the time of the collision.
"""


def generate_party_section(party_details):
    prompt = f"""
{NO_HALLUCINATION_NOTE}
{LEGAL_FLUENCY_NOTE}

Write a “Parties” section using only the information below. Describe the Plaintiff and all Defendants, including any employer or corporate affiliations. Keep it factual, professional, and concise.

Example:
{PARTIES_EXAMPLE}

Input:
{party_details}
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


# === Placeholder Replacer ===
def replace_placeholders(doc, replacements):
    def replace_in_paragraph(paragraph: Paragraph):
        full_text = paragraph.text
        for key, val in replacements.items():
            if key in full_text:
                full_text = full_text.replace(key, val)
        if paragraph.runs:
            paragraph.clear()
            paragraph.add_run(full_text)

    def replace_in_cell(cell: _Cell):
        for paragraph in cell.paragraphs:
            replace_in_paragraph(paragraph)

    for paragraph in doc.paragraphs:
        replace_in_paragraph(paragraph)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                replace_in_cell(cell)

# === Template Filler ===

def fill_mediation_template(data, template_path, output_path):
    doc = Document(template_path)

    # Start with static placeholders
    replacements = {
        "{{Court}}": data.get("court", ""),
        "{{Plaintiff}}": data.get("plaintiff", ""),
        "{{Case Number}}": data.get("case_number", ""),
        "{{Introduction}}": data.get("introduction", ""),
        "{{Parties}}": data.get("parties", ""),
        "{{Plaintiff Statement}}": data.get("plaintiff_statement", ""),
        "{{Demand}}": data.get("demand", ""),
        "{{Facts/Liability}}": data.get("facts_liability", ""),
        "{{Causation, Injuries, and Treatment}}": data.get("causation_injuries", ""),
        "{{Additional Harms and Losses}}": data.get("additional_harms", ""),
        "{{Future Medical Bills Related to the Collision}}": data.get("future_bills", ""),
        "{{Conclusion}}": data.get("conclusion", "")
    }

    # Add up to 3 plaintiffs
    for i in range(1, 4):
        replacements[f"{{{{Plaintiff{i}}}}}"] = data.get(f"plaintiff{i}", "")
        replacements[f"{{{{Plaintiff{i} Statement}}}}"] = data.get(
            f"plaintiff{i}_statement", "")

    # Dynamically add up to 7 defendants
    for i in range(1, 8):
        replacements[f"{{{{Defendant{i}}}}}"] = data.get(f"defendant{i}", "")
        replacements[f"{{{{Defendant{i} Statement}}}}"] = data.get(
            f"defendant{i}_statement", "")

    replace_placeholders(doc, replacements)

    filename = f"Mediation_Memo_{data.get('plaintiff', '').replace(' ', '_')}_{datetime.today().strftime('%Y-%m-%d')}.docx"
    output_file_path = os.path.join(output_path, filename)
    doc.save(output_file_path)

    return output_file_path



# --- Safe wrapper to handle OpenAI rate limits ---


def safe_generate(fn, *args, retries=3, wait_time=10):
    for attempt in range(retries):
        try:
            return fn(*args)
        except APIStatusError as e:
            if e.status_code == 429 and "rate_limit_exceeded" in str(e):
                st.warning(
                    f"Rate limit hit. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("❌ gpt-3.5-turbo rate limit error after multiple attempts.")

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
def generate_quotes_in_chunks(text_chunks, delay_seconds=10):
    """
    Generate categorized Q&A quotes for each chunk with line numbers preserved.
    Organize quotes into specific categories and combine all results at the end.
    """
    all_quotes = []

    for i, chunk in enumerate(text_chunks):
        prompt = f"""
You are a legal analyst reviewing deposition testimony. Each line starts with a number and a "Q" or "A".

Your task is to extract **only relevant Q&A pairs** into the correct categories listed below.

For each category, return a **bulleted list of line-numbered pairs**, like this:

- Q123: "Full question here?"
  A124: "Exact answer here."

⚠️ Follow these rules:
- DO NOT paraphrase.
- DO NOT summarize.
- DO NOT include answers without a corresponding question.
- DO NOT remove or guess line numbers.
- DO NOT output anything else besides direct Q&A in the format above.If no quotes exist for a category, write: "None found."

📂 Categories:
1. Responsibility or Duties of the Witness  
2. Knowledge of Events or Conditions Related to the Incident  
3. Cause or Contributing Factors to the Incident  
4. Resulting Injuries, Damages, or Losses  
5. Changes in Quality of Life, Function, or Employment  


Only include direct testimony. Do not paraphrase. Do not include commentary. Skip any irrelevant lines.

Organize your output into the following categories:

1. Responsibility for patching the road  
2. Responsibility for traffic control or maintaining traffic control  
3. Causation of the incident or hazard  
4. Damages or injuries resulting from the incident  
5. Harm to quality of life after the incident  

If nothing is found for a category, write: "None found."

Deposition excerpt:
{chunk}
"""
        try:
            quotes = safe_generate(generate_with_openai, prompt)
            all_quotes.append(quotes)
            print(f"Processed chunk {i+1}/{len(text_chunks)}")
        except APIStatusError as e:
            print(f"API error on chunk {i+1}: {e}")
            raise e

        if i < len(text_chunks) - 1:
            time.sleep(delay_seconds)  # delay to avoid rate limit

    combined_quotes = "\n\n".join(all_quotes)
    return combined_quotes


# --- Main generation function ---
def generate_memo_from_summary(data, template_path, output_dir):
    memo_data = {}

    memo_data["court"] = data["court"]
    memo_data["case_number"] = data["case_number"]
    # Determine primary plaintiff
    plaintiff1 = data.get("plaintiff1") or data.get("plaintiff") or "Plaintiff"
    memo_data["plaintiff"] = plaintiff1
    memo_data["plaintiff1"] = plaintiff1
    memo_data["plaintiff1_statement"] = safe_generate(
        generate_plaintiff_statement, data["complaint_narrative"], plaintiff1)

    # Handle up to 3 plaintiffs
    for i in range(2, 4):
        name = data.get(f"plaintiff{i}", "").strip()
        if name:
            memo_data[f"plaintiff{i}"] = name
            memo_data[f"plaintiff{i}_statement"] = safe_generate(
                generate_plaintiff_statement, data["complaint_narrative"], name)

    # Handle up to 7 defendants dynamically
    for i in range(1, 8):
        key = f"defendant{i}"
        name = data.get(key, "")
        memo_data[key] = name
        if name:
            memo_data[f"{key}_statement"] = safe_generate(
                generate_defendant_statement, data["complaint_narrative"], name)
        else:
            memo_data[f"{key}_statement"] = ""

    # Main body content
    memo_data["introduction"] = safe_generate(
        generate_introduction, data["complaint_narrative"], plaintiff1)
    memo_data["demand"] = safe_generate(
        generate_demand_section, data["settlement_summary"], plaintiff1)

    all_quotes_pool = data.get("all_quotes_pool", "")

    memo_data["facts_liability"] = safe_generate(
        generate_facts_liability_section,
        data["complaint_narrative"],  
        all_quotes_pool              
    )

    memo_data["additional_harms"] = safe_generate(
        generate_additional_harms,
        data["medical_summary"],      
        all_quotes_pool               
    )

    memo_data["future_bills"] = safe_generate(
        generate_future_medical,
        data["medical_summary"],      
        all_quotes_pool              
    )

    memo_data["conclusion"] = safe_generate(
        generate_conclusion_section, data["settlement_summary"])

    return fill_mediation_template(memo_data, template_path, output_dir)
