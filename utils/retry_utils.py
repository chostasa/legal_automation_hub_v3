from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
from openai import OpenAIError  

# === Retry for OpenAI API errors (rate limits, unavailability) ===
openai_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(OpenAIError)
)

# === Retry for HTTP API errors (Graph, NEOS, Dropbox, etc.) ===
http_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
