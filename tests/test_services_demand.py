import pytest
from services import demand_service

def test_generate_demand_invalid_inputs():
    with pytest.raises(Exception):
        demand_service.generate_demand_letter(
            client_name="", defendant="", location="", incident_date="", summary="", damages="",
            template_path="missing.docx", output_path="output.docx", example_text=""
        )
