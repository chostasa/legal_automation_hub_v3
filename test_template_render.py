from docxtpl import DocxTemplate
import traceback
import os

TEMPLATE_PATH = "templates/foia_template.docx"

# 🔧 Test values
test_data = {
    "date": "July 24, 2025",
    "client_id": "JANE-ROE-001",
    "defendant_name": "Records Custodian",
    "defendant_line1": "123 Main St.",
    "defendant_line2": "Chicago, IL 60601",
    "location": "Chicago Juvenile Detention Center",
    "doi": "June 1, 2023",
    "synopsis": "Client was assaulted by staff in a secured wing. She suffered severe head trauma and permanent neurological damage.",
    "foia_request_bullet_points": "• All internal reports\n• Surveillance video\n• Staff rosters\n• Communication logs",
    "Body": "This FOIA request pertains to the incident involving Jane Roe on June 1, 2023. Please provide the requested materials below within the statutory time period.",
    "state_citation": "Pursuant to the Illinois FOIA Act, 5 ILCS 140/1 et seq.",
    "state_response_time": "We expect a response within 5 business days as required by Illinois law.",
}

# ✅ Step 1: Confirm template loads and placeholder integrity
print(f"\n🔍 Checking template: {TEMPLATE_PATH}")
try:
    doc = DocxTemplate(TEMPLATE_PATH)
    placeholders = doc.get_undeclared_template_variables()
    print(f"✅ Found placeholders: {placeholders}")
except Exception as e:
    print(f"❌ Error loading template:")
    traceback.print_exc()
    exit(1)

# ✅ Step 2: Try rendering with each variable individually
print("\n🧪 Testing each variable in isolation:")
for key in test_data:
    print(f"\n🔹 Testing: {key}")
    try:
        doc = DocxTemplate(TEMPLATE_PATH)
        partial_context = {key: test_data[key]}
        doc.render(partial_context)
        print(f"✅ Successfully rendered with only '{key}'")
    except Exception as e:
        print(f"❌ Rendering failed with only '{key}':")
        traceback.print_exc()

# ✅ Step 3: Try rendering full context
print("\n🧪 Testing full context render:")
try:
    doc = DocxTemplate(TEMPLATE_PATH)
    doc.render(test_data)
    print("✅ Full context render succeeded.")
except Exception as e:
    print("❌ Full context render failed:")
    traceback.print_exc()
