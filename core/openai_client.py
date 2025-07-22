# core/openai_client.py

import openai
import time
from logger import logger
from core.security import redact_log

openai.api_key = os.getenv("OPENAI_API_KEY", "")  # Ensure key is loaded from environment

def safe_generate(system_prompt: str, user_prompt: str, max_retries: int = 3, model: str = "gpt-3.5-turbo") -> str:
    """
    Generates content using OpenAI with retries and error handling.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6
            )
            return response.choices[0].message.content.strip()

        except openai.error.RateLimitError:
            wait_time = 2 ** attempt
            logger.warning(f"⏳ OpenAI rate limit hit. Retrying in {wait_time}s...")
            time.sleep(wait_time)

        except Exception as e:
            logger.error(redact_log(f"❌ OpenAI error (attempt {attempt}): {e}"))
            time.sleep(1)

    raise RuntimeError("❌ Failed to generate OpenAI response after retries.")
