from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
from openai import OpenAIError
from core.error_handling import handle_error


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(OpenAIError)
)
def openai_retry(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except OpenAIError as e:
        handle_error(e, "OPENAI_RETRY_FAIL")
        raise


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def http_retry(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except requests.exceptions.RequestException as e:
        handle_error(e, "HTTP_RETRY_FAIL")
        raise
