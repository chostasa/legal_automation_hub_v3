from docxtpl import DocxTemplate
import traceback
from core.security import sanitize_text

def test_demand_template(template_path, sections):
    context = {
        "{{ClientName}}": "John Doe",
        "{{Defendant}}": "ABC Corp.",
        "{{Location}}": "Springfield, IL",
        "{{IncidentDate}}": "2023-04-10",
        "{{BriefSynopsis}}": sanitize_text(sections["brief_synopsis"]),
        "{{Demand}}": sanitize_text(sections["demand"]),
        "{{Damages}}": sanitize_text(sections["damages"]),
        "{{SettlementDemand}}": sanitize_text(sections["settlement"]),
    }

    try:
        print("🔍 Loading template...")
        doc = DocxTemplate(template_path)

        print("🧪 Rendering context:")
        for k, v in context.items():
            print(f"   {k}: {repr(v)[:80]}")

        doc.render(context)
        print("✅ Template rendered successfully!")

    except Exception as e:
        print("❌ Template rendering failed:", e)
        traceback.print_exc()
        try:
            doc.dump("debug_template_error")
            print("📄 Dumped to debug_template_error.xml")
        except Exception as dump_error:
            print("⚠️ Failed to dump:", dump_error)

if __name__ == "__main__":
    test_demand_template(
        template_path="templates/demand_template.docx",
        sections={
            "brief_synopsis": "Client was struck while walking in the crosswalk...",
            "demand": "Defendant failed to yield, causing substantial harm.",
            "damages": "Client suffered a fractured pelvis, requiring surgery.",
            "settlement": "We are demanding $750,000 to resolve this matter.",
        }
    )
