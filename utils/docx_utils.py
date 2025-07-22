import os
import zipfile
import shutil
from lxml import etree
from utils.template_engine import render_docx_placeholders

NAMESPACES = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

# These are the .docx parts to scan for placeholder text
TARGET_XML_FILES = [
    "word/document.xml",
    "word/header1.xml", "word/header2.xml", "word/header3.xml",
    "word/footer1.xml", "word/footer2.xml", "word/footer3.xml",
    "word/comments.xml"  # Optional: tracks comment placeholders if used
]

def replace_text_in_docx_all(docx_path: str, replacements: dict, save_path: str) -> str:
    """
    Replaces all placeholders in a .docx file using Jinja2 rendering and saves the result to `save_path`.
    Handles paragraphs, tables, headers, footers, and inline <w:t> text runs in known XML parts.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    with zipfile.ZipFile(docx_path, 'r') as zin:
        with zipfile.ZipFile(save_path, 'w') as zout:
            for item in zin.infolist():
                buffer = zin.read(item.filename)

                # Only transform editable Word content (headers, body, footers, etc.)
                if item.filename in TARGET_XML_FILES:
                    try:
                        xml = etree.fromstring(buffer)

                        # Find all text nodes in Word markup
                        for node in xml.xpath('//w:t', namespaces=NAMESPACES):
                            if node.text:
                                rendered = render_docx_placeholders(node.text, replacements)
                                node.text = rendered

                        buffer = etree.tostring(xml, xml_declaration=True, encoding='utf-8')

                    except Exception as e:
                        raise RuntimeError(f"Failed to parse and render {item.filename}: {e}")

                zout.writestr(item, buffer)

    return save_path

