import pytest
from services import memo_service

def test_generate_memo_fields_missing_template():
    with pytest.raises(Exception):
        memo_service.generate_memo_from_fields(
            data={}, template_path="missing.docx", output_dir="."
        )
