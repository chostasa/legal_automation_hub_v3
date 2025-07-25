# ui/instructions_ui.py

import streamlit as st

def run_ui():
    st.title("📖 Legal Automation Hub: Full Instructions & Training")

    st.markdown("""
# ⚡ Welcome to the Legal Automation Hub  

This hub was built to make your litigation campaigns faster and easier.  
Each section below explains **exactly what you need to do** with pictures (coming soon) and videos (coming soon).  

---

## 📂 **Demand Letter Generator**

**What this tool does:**  
Generates fully formatted demand letters (.docx files) for clients, ready to send.  

### Step-by-Step:
1. **Open the Demand Letter Generator** from the sidebar.  
2. **Fill in the form:**  
   - **Client Name:** Type the client's full name (e.g., *Jane Roe*).  
   - **Defendant Name:** Who the letter is sent to (e.g., *City of Chicago*).  
   - **Incident Date:** Use the calendar to select the exact date.  
   - **Location of Incident:** Type the address or location name.  
   - **Summary of Incident:** One paragraph summarizing what happened.  
   - **Damages Summary:** One paragraph describing the impact/injuries.  
3. *(Optional)* Click **Style/Tone Example** and upload a sample letter. This helps the AI match the firm’s voice.  
4. **Click “⚙️ Generate Demand Letter”.**  
   - It will take a few seconds.  
   - When complete, a **green success message** will appear.  
5. **Click the Download button** to save the Word file (.docx) to your computer.  
6. The file is now ready to send or upload into NEOS.

---

## 📬 **FOIA Letter Generator**

**What this tool does:**  
Generates Freedom of Information Act letters asking for records.  

### Step-by-Step:
1. **Open the FOIA Letter Generator** from the sidebar.  
2. Fill in each box carefully:  
   - **Client ID:** Enter the client’s full name or ID number.  
   - **Recipient Name:** The agency or person you’re requesting records from.  
   - **Recipient Address:** Enter the full mailing address.  
   - **State:** Choose the state where the request will be sent.  
   - **Date of Incident:** Select the date of the event.  
   - **Location:** The exact address or place where it happened.  
   - **Case Synopsis:** Short explanation (2–3 sentences) of what happened.  
   - **Potential Requests:** List the records you expect (e.g., *police reports, body camera footage*).  
   - **Explicit Instructions:** Any special notes.  
   - **Case Type, Facility/System, Recipient Role:** Fill in based on the case context.  
3. *(Optional)* Add a Style Example file.  
4. **Click “⚙️ Generate FOIA Letter”.**  
5. Review the **bullet list of records** that will appear on-screen.  
6. **Download the FOIA Letter (.docx)** using the button.  

---

## 🗞 **Mediation Memo Generator**

**What this tool does:**  
Creates detailed mediation memos with deposition quotes built in.  

### Step-by-Step:
1. **Open the Mediation Memo Generator**.  
2. Fill in the **Case Details:**  
   - Court name (e.g., *Cook County Circuit Court*)  
   - Case Number  
3. Fill in **Plaintiffs and Defendants:** Enter each name in its box.  
4. Enter:  
   - Complaint Narrative (summary of the complaint)  
   - Party Information (optional)  
   - Settlement Summary  
   - Medical Summary  
   - Future Medical Bills (optional)  
5. *(Optional)* Paste deposition transcript text in the large box to pull out quotes.  
6. Upload the **Mediation Memo Template (.docx)**.  
7. Choose **Preview Party Paragraphs** (to edit summaries) OR **Generate Memo** (full memo).  
8. **Download the .docx or Plain Text Preview.**  

---

## 📊 **Litigation Dashboard**

**What this tool does:**  
Shows a live view of all cases and campaigns.  

### Step-by-Step:
1. **Open the Dashboard**.  
2. Use the filters on the **left-hand sidebar**:  
   - Select by Campaign  
   - Select by Referring Attorney  
   - Select by Case Status  
3. Scroll down to see the tables and charts update live.  
4. **Download results** as CSV or send filtered data to **Batch Document Generator**.  

---

## 📄 **Batch Document Generator**

**What this tool does:**  
Takes a spreadsheet of client data + a Word template and generates personalized letters for everyone in one batch.  

### Step-by-Step:
1. **Open the Batch Document Generator.**  
2. Upload an **Excel file (.xlsx)** of client data OR use filtered data from the Dashboard.  
3. Verify the column headers match the placeholders (e.g., `{{Client Name}}`).  
4. Choose:  
   - **Upload New Template:** Pick a Word template from your computer.  
   - **Select Saved Template:** Pick from templates already stored in the Hub.  
5. *(Optional)* Remove columns you don’t want to include.  
6. **Click “⚙️ Generate Documents”.**  
7. A ZIP file containing all the merged letters will be ready to **download**.  

---

## 📧 **Email Automation**

**What this tool does:**  
Sends intake/welcome emails to multiple clients and updates their NEOS status.  

### Step-by-Step:
1. **Open the Email Automation tool.**  
2. Filter clients:  
   - Only those with certain Class Codes (e.g., Intake Complete).  
   - By status, email, or name.  
3. **Select a template** from the dropdown.  
4. Preview each email:  
   - You can edit the Subject and Body before sending.  
5. Send emails **one-by-one** or click **Send All**.  
6. Each email is logged automatically.  

---

## 🧠 **Style Mimic Generator**

**What this tool does:**  
Takes example paragraphs and rewrites other text in the same style.  

### Step-by-Step:
1. Paste example paragraphs in the box (separate with `---`).  
2. Choose **Upload Excel** OR **Paste Text Inputs**.  
3. Click **Generate Styled Outputs**.  
4. Download results as an Excel file with side-by-side Original and Styled text.  

---

## 🧪 **Template Tester**

**What this tool does:**  
Shows you how a template will render before you use it.  

### Step-by-Step:
1. Upload the **Word template (.docx)** you want to test.  
2. Paste sample data in JSON or YAML format (instructions are in the box).  
3. Click **Generate Preview**.  
4. Download the previewed template.  

---

## 🎥 Training Videos (Coming Soon)

Video tutorials will be added here for each section.  

""")
