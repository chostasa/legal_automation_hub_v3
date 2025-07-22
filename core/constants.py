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

# ----------------------------
# 📧 Default Email Settings
# ----------------------------
DEFAULT_SENDER_EMAIL = os.getenv("DEFAULT_SENDER_EMAIL", "noreply@yourdomain.com")

# ----------------------------
# 📁 Template Directory for Batch Generator
# ----------------------------
TEMPLATE_DIR = "templates"
