import os
import zipfile
import html
from lxml import etree
from utils.template_engine import render_docx_placeholders
from docx import Document
from core.security import mask_phi, redact_log
from core.error_handling import handle_error
from utils.file_utils import validate_file_size
from core.audit import log_audit_event
from logger import logger
import hashlib
import datetime

NAMESPACES = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

TARGET_XML_FILES = [
    "word/document.xml",
    "word/header1.xml", "word/header2.xml", "word/header3.xml",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
    "word/comments.xml",
    "word/vbaProject.bin"
]

def _hash_template_version(file_path: str) -> str:
    """
    Compute SHA256 hash for template version tracking.
    """
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        handle_error(e, code="DOCX_HASH_001", raise_it=True)

def _scan_for_macros(docx_path: str):
    """
    Scan the template for suspicious macros and log them.
    """
    try:
        if not os.path.exists(docx_path):
            raise FileNotFoundError(f"File does not exist: {docx_path}")

        with zipfile.ZipFile(docx_path, 'r') as zin:
            for item in zin.infolist():
                if "vbaProject" in item.filename.lower() or item.filename.endswith(".bin"):
                    log_audit_event("Macro Detected", {"file": docx_path, "item": item.filename})
                    logger.error(redact_log(mask_phi(f"Macro detected in template: {item.filename}")))
                    raise ValueError(f"Macros detected in template: {item.filename}")
    except Exception as e:
        handle_error(e, code="DOCX_MACRO_001", raise_it=True)

def replace_text_in_docx_all(docx_path: str, replacements: dict, save_path: str) -> str:
    """
    Replace placeholders in all major parts of a Word template,
    write to a new versioned file, and log the version.
    """
    try:
        if not isinstance(replacements, dict):
            raise ValueError("Replacements must be provided as a dictionary.")
        if not replacements:
            raise ValueError("Replacements dictionary cannot be empty.")
        if not os.path.isfile(docx_path):
            raise FileNotFoundError(f"Input DOCX file does not exist: {docx_path}")

        validate_file_size(docx_path)
        _scan_for_macros(docx_path)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        replacements = {
            k: html.unescape(str(v)) if not isinstance(v, list)
            else [html.unescape(str(x)) for x in v]
            for k, v in replacements.items()
        }

        with zipfile.ZipFile(docx_path, 'r') as zin:
            with zipfile.ZipFile(save_path, 'w') as zout:
                for item in zin.infolist():
                    buffer = zin.read(item.filename)

                    if item.filename in TARGET_XML_FILES:
                        try:
                            xml = etree.fromstring(buffer)
                            for node in xml.xpath('//w:t', namespaces=NAMESPACES):
                                if node.text:
                                    rendered = render_docx_placeholders(node.text, replacements)
                                    node.text = html.unescape(rendered)
                            buffer = etree.tostring(xml, xml_declaration=True, encoding='utf-8')
                        except Exception as e:
                            handle_error(e, code="DOCX_PARSE_001", raise_it=True)

                    zout.writestr(item, buffer)

        doc = Document(save_path)
        for para in doc.paragraphs:
            for key, val in replacements.items():
                placeholder = f"{{{{{key}}}}}"
                if para.text.strip() == placeholder:
                    if isinstance(val, list):
                        for bullet in val:
                            if bullet.strip():
                                new_para = para.insert_paragraph_before(bullet.strip())
                                new_para.style = "List Bullet"
                        para.text = ""
                    else:
                        para.text = para.text.replace(placeholder, str(val))

        if not os.path.isfile(save_path):
            raise FileNotFoundError(f"Output DOCX was not created: {save_path}")

        doc.save(save_path)
        version_hash = _hash_template_version(save_path)
        log_audit_event("DOCX Replace Completed", {
            "file": save_path,
            "version_hash": version_hash,
            "timestamp": datetime.datetime.utcnow().isoformat()
        })
        logger.info(redact_log(mask_phi(
            f"DOCX replacement completed for {save_path}, version {version_hash}"
        )))
        return save_path

    except Exception as e:
        handle_error(e, code="DOCX_REPLACE_001", raise_it=True)
