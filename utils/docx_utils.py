import os
import zipfile
import html
import datetime
import hashlib
from lxml import etree
from utils.template_engine import render_docx_placeholders
from docx import Document
from core.security import mask_phi, redact_log
from core.error_handling import handle_error
from utils.file_utils import validate_file_size
from core.audit import log_audit_event
from core.auth import get_tenant_id
from utils.thread_utils import run_in_thread
from logger import logger

NAMESPACES = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

TARGET_XML_FILES = [
    "word/document.xml",
    "word/header1.xml", "word/header2.xml", "word/header3.xml",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
    "word/comments.xml",
    "word/vbaProject.bin"
]

def _hash_template_version(file_path: str) -> str:
    """Compute a SHA256 hash of the file for versioning."""
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def _scan_for_macros(docx_path: str):
    """
    Scan DOCX for macros and fail if a real macro (vbaProject.bin) is found.
    Warn only for other .bin files.
    """
    try:
        if not os.path.exists(docx_path):
            raise FileNotFoundError(f"File does not exist: {docx_path}")

        with zipfile.ZipFile(docx_path, 'r') as zin:
            for item in zin.infolist():
                if "vbaProject.bin" in item.filename.lower():
                    log_audit_event("Macro Detected", {
                        "file": docx_path,
                        "item": item.filename,
                        "tenant_id": get_tenant_id()
                    })
                    logger.error(redact_log(mask_phi(
                        f"⚠️ Macro detected in {docx_path}:{item.filename}"
                    )))
                    raise ValueError(f"Macros detected in template: {item.filename}")
                elif item.filename.endswith(".bin"):
                    logger.warning(redact_log(mask_phi(
                        f"⚠️ Non-critical .bin resource detected: {item.filename}"
                    )))
    except Exception as e:
        handle_error(e, code="DOCX_MACRO_001", raise_it=True)

def replace_text_in_docx_all(docx_path: str, replacements: dict, save_path: str) -> str:
    """
    Replace placeholders in all major XML parts of a DOCX template, save a new version,
    and log a version hash for audit purposes.
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

        # Ensure directory exists for save_path
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Decode HTML entities in replacements
        replacements = {
            k: html.unescape(str(v)) if not isinstance(v, list)
            else [html.unescape(str(x)) for x in v]
            for k, v in replacements.items()
        }

        # Wrap the heavy zip I/O in a background thread for better concurrency
        def _replace_zip():
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

        run_in_thread(_replace_zip)

        # Post-processing: handle bullet lists and placeholders
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

        # Save and audit
        doc.save(save_path)
        version_hash = _hash_template_version(save_path)
        log_audit_event("DOCX Replace Completed", {
            "file": save_path,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "version_hash": version_hash,
            "tenant_id": get_tenant_id()
        })
        logger.info(redact_log(mask_phi(
            f"✅ DOCX replace completed for {save_path}, version: {version_hash}"
        )))
        return save_path

    except Exception as e:
        handle_error(e, code="DOCX_REPLACE_001", raise_it=True)
