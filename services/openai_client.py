from openai import OpenAI, OpenAIError
from config_loader import AppConfig, get_config
from utils.retry_utils import openai_retry
from utils.token_utils import trim_to_token_limit
from core.security import redact_log
from core.usage_tracker import log_usage
from core.auth import get_user_id, get_tenant_id
from logger import logger

# ✅ Use only tested alias, avoid versioned IDs
DEFAULT_MODEL = "gpt-4"
DEFAULT_SYSTEM_MSG = "You are a professional legal writer. Stay concise and legally fluent."

class OpenAIClient:
    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.client = OpenAI(api_key=self.config.OPENAI_API_KEY)
        self.model = getattr(self.config, "OPENAI_MODEL", DEFAULT_MODEL)

    @openai_retry
    def safe_generate(
        self,
        prompt: str,
        model: str = None,
        system_msg: str = DEFAULT_SYSTEM_MSG,
        temperature: float = 0.4
    ) -> str:
        try:
            trimmed = trim_to_token_limit(prompt)

            # ✅ Force model to known good default if invalid
            used_model = model or self.model or DEFAULT_MODEL
            if used_model not in ["gpt-3.5-turbo", "gpt-4"]:
                logger.warning(f"⚠️ Invalid model requested: {used_model}. Falling back to {DEFAULT_MODEL}")
                used_model = DEFAULT_MODEL

            response = self.client.chat.completions.create(
                model=used_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": trimmed}
                ],
                temperature=temperature
            )

            choices = getattr(response, "choices", [])
            if not choices:
                raise RuntimeError("❌ OpenAI returned no completions.")

            content = choices[0].message.content.strip()

            usage = getattr(response, "usage", None)
            if usage:
                log_usage(
                    event_type="openai_tokens",
                    tenant_id=get_tenant_id(),
                    user_id=get_user_id(),
                    amount=usage.total_tokens,
                    metadata={
                        "model": used_model,
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                    }
                )

            return content

        except OpenAIError as e:
            logger.error(redact_log(f"❌ OpenAI API error: {e}"))
            raise RuntimeError("OpenAI generation failed due to API error.")

        except Exception as e:
            logger.error(redact_log(f"❌ Unexpected OpenAI failure: {e}"))
            raise RuntimeError("OpenAI generation failed unexpectedly.")

openai_client_instance = OpenAIClient()

@openai_retry
def safe_generate(
    prompt: str,
    model: str = None,
    system_msg: str = DEFAULT_SYSTEM_MSG,
    temperature: float = 0.4
) -> str:
    return openai_client_instance.safe_generate(
        prompt=prompt,
        model=model,
        system_msg=system_msg,
        temperature=temperature
    )
