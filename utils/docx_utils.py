import os
import zipfile
import shutil
import pypandoc
from lxml import etree
from utils.template_engine import render_docx_placeholders

def replace_text_in_docx_all(docx_path: str, replacements: dict, save_path: str) -> str:
    """
    Replaces all placeholders in a .docx file using Jinja2 rendering and saves the result to `save_path`.
    Handles textboxes, paragraphs, tables, and any inline <w:t> nodes in word/document.xml.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    with zipfile.ZipFile(docx_path, 'r') as zin:
        with zipfile.ZipFile(save_path, 'w') as zout:
            for item in zin.infolist():
                buffer = zin.read(item.filename)

                if item.filename == 'word/document.xml':
                    try:
                        xml = etree.fromstring(buffer)
                        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

                        for node in xml.xpath('//w:t', namespaces=ns):
                            if node.text:
                                rendered = render_docx_placeholders(node.text, replacements)
                                node.text = rendered

                        buffer = etree.tostring(xml, xml_declaration=True, encoding='utf-8')
                    except Exception as e:
                        raise RuntimeError(f"Failed to parse and render placeholders: {e}")

                zout.writestr(item, buffer)

    return save_path


def convert_to_pdf(docx_path: str, pdf_path: str) -> str:
    """
    Converts a .docx file to .pdf using Pandoc.
    Requires pandoc + LibreOffice installed on system.
    """
    if not shutil.which("pandoc"):
        raise RuntimeError("pandoc is not installed. Install from https://pandoc.org/installing.html")

    try:
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        pypandoc.convert_file(docx_path, 'pdf', outputfile=pdf_path)
        return pdf_path
    except Exception as e:
        raise RuntimeError(f"PDF conversion failed: {e}")
