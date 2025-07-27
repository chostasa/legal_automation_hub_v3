import pytest
from services import foia_service

def test_generate_foia_invalid_template():
    with pytest.raises(Exception):
        foia_service.generate_foia_letter(
            data={}, template_path="missing.docx", output_path="output.docx"
        )
