import os

# ----------------------------
# 📌 Status Labels (UI/Logic)
# ----------------------------
STATUS_INTAKE_COMPLETED = "Intake Completed"
STATUS_QUESTIONNAIRE_SENT = "Questionnaire Sent"

STATUS_CHOICES = [
    STATUS_INTAKE_COMPLETED,
    STATUS_QUESTIONNAIRE_SENT
]

# ----------------------------
# 📄 Template Paths
# ----------------------------
TEMPLATE_DEMAND = "templates/demand_template.docx"
TEMPLATE_FOIA = "templates/foia_template.docx"
TEMPLATE_DIR = "templates"

# Backward compatibility for legacy imports
demand_template = TEMPLATE_DEMAND
foia_template = TEMPLATE_FOIA

# ----------------------------
# 📧 Default Email Settings
# ----------------------------
DEFAULT_SENDER_EMAIL = os.getenv("DEFAULT_SENDER_EMAIL", "noreply@yourdomain.com")

DROPBOX_TEMPLATES_ROOT = "/Legal Automation Hub/LegalAutomationHub/templates"
DROPBOX_EXAMPLES_ROOT = "/Legal Automation Hub/LegalAutomationHub/examples"


