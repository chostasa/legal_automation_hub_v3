from dotenv import load_dotenv
import pytest
import os

# Load .env.test
load_dotenv(".env.test")

# Optional: confirm config loaded
assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not loaded"

# Run tests
pytest.main(["tests"])
