import os
import zipfile
import shutil
import html
from lxml import etree
from utils.template_engine import render_docx_placeholders
from docx import Document

NAMESPACES = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# Editable Word XML parts to search for placeholders
TARGET_XML_FILES = [
    "word/document.xml",
    "word/header1.xml", "word/header2.xml", "word/header3.xml",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
    "word/comments.xml"
]

def replace_text_in_docx_all(docx_path: str, replacements: dict, save_path: str) -> str:
    """
    Replaces placeholders in all major parts of a Word .docx file and saves it to `save_path`.
    Supports rendering with Jinja2, and handles list values by inserting real bullet paragraphs.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    # Ensure replacements are unescaped first
    replacements = {k: html.unescape(str(v)) if not isinstance(v, list)
                    else [html.unescape(str(x)) for x in v]
                    for k, v in replacements.items()}

    # Step 1: Copy zip contents and modify XML
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
                                # Unescape any HTML entities in rendered text
                                node.text = html.unescape(rendered)

                        buffer = etree.tostring(xml, xml_declaration=True, encoding='utf-8')
                    except Exception as e:
                        raise RuntimeError(f"❌ Failed to parse and render {item.filename}: {e}")

                zout.writestr(item, buffer)

    # Step 2: Open modified file and insert real bullets for List[str] values
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
                    para.text = ""  # Clear original placeholder
                else:
                    para.text = para.text.replace(placeholder, str(val))

    doc.save(save_path)
    return save_path
