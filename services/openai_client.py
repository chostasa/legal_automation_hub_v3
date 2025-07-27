from openai import OpenAI, OpenAIError
from config_loader import AppConfig, get_config
from utils.retry_utils import openai_retry
from utils.token_utils import trim_to_token_limit
from core.security import redact_log, mask_phi
from core.usage_tracker import log_usage
from core.auth import get_user_id, get_tenant_id
from core.error_handling import handle_error, AppError
from logger import logger

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
        temperature: float = 0.4,
        test_mode: bool = False,
    ) -> str:
        """
        Generate text using the OpenAI API with safety checks, error codes, and usage logging.
        Includes test hooks and optional deterministic mode.
        """
        try:
            tenant_id = get_tenant_id()
            user_id = get_user_id()

            # Trim prompt to avoid token overflows
            trimmed = trim_to_token_limit(prompt)

            # Validate model
            used_model = model or self.model or DEFAULT_MODEL
            if used_model not in ["gpt-3.5-turbo", "gpt-4"]:
                logger.warning(
                    redact_log(
                        mask_phi(
                            f"⚠️ Invalid model requested: {used_model}. Falling back to {DEFAULT_MODEL}"
                        )
                    )
                )
                used_model = DEFAULT_MODEL

            # Optional test mode returns deterministic output for integration tests
            if test_mode:
                logger.info("[OPENAI_GEN_TEST] Returning deterministic test output.")
                return f"[TEST MODE] Prompt length={len(trimmed)} Model={used_model}"

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=used_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": trimmed},
                ],
                temperature=temperature,
            )

            # Validate response
            choices = getattr(response, "choices", [])
            if not choices or not hasattr(choices[0], "message"):
                raise AppError(
                    code="OPENAI_GEN_001",
                    message="OpenAI returned no completions.",
                    details=f"Model={used_model}, Prompt length={len(trimmed)}",
                )

            # Extract content
            content = choices[0].message.content.strip()

            # Log usage tokens
            usage = getattr(response, "usage", None)
            if usage:
                log_usage(
                    event_type="openai_tokens",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    amount=usage.total_tokens,
                    metadata={
                        "model": used_model,
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                    },
                )

            return content

        except OpenAIError as e:
            # API-specific errors
            handle_error(
                e,
                code="OPENAI_GEN_002",
                user_message="OpenAI API error occurred. Please try again later.",
                raise_it=True,
            )

        except AppError:
            # Already wrapped errors
            raise

        except Exception as e:
            # Catch-all
            handle_error(
                e,
                code="OPENAI_GEN_003",
                user_message="Unexpected error during text generation.",
                raise_it=True,
            )


# === Singleton Instance ===
openai_client_instance = OpenAIClient()


@openai_retry
def safe_generate(
    prompt: str,
    model: str = None,
    system_msg: str = DEFAULT_SYSTEM_MSG,
    temperature: float = 0.4,
    test_mode: bool = False,
) -> str:
    """
    Wrapper function for modules that want to call OpenAI without importing the class.
    Supports test_mode for Phase 5 test hooks.
    """
    return openai_client_instance.safe_generate(
        prompt=prompt,
        model=model,
        system_msg=system_msg,
        temperature=temperature,
        test_mode=test_mode,
    )
