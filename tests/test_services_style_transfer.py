import pytest
from services import style_transfer_service

def test_run_batch_style_transfer_empty_inputs():
    import pandas as pd
    with pytest.raises(Exception):
        style_transfer_service.run_batch_style_transfer([], pd.DataFrame())
