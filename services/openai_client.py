import asyncio
import time
from openai import AsyncOpenAI, OpenAIError
from config_loader import AppConfig, get_config
from utils.retry_utils import openai_retry
from utils.token_utils import trim_to_token_limit
from core.security import redact_log, mask_phi
from core.usage_tracker import log_usage, check_quota
from core.auth import get_user_id, get_tenant_id, get_user_role
from core.error_handling import handle_error, AppError
from logger import logger

# Default constants
DEFAULT_MODEL = "gpt-4"
DEFAULT_SYSTEM_MSG = "You are a professional legal writer. Stay concise and legally fluent."


class OpenAIClient:
    """
    Async wrapper around the OpenAI API with retry, quota enforcement,
    token trimming, and audit logging.
    """

    def __init__(self, config: AppConfig = None):
        self.config = config or get_config()
        self.client = AsyncOpenAI(api_key=self.config.OPENAI_API_KEY)
        self.model = getattr(self.config, "OPENAI_MODEL", DEFAULT_MODEL)

    @openai_retry
    async def safe_generate(
        self,
        prompt: str,
        model: str = None,
        system_msg: str = DEFAULT_SYSTEM_MSG,
        temperature: float = 0.4,
        test_mode: bool = False,
    ) -> str:
        """
        Safely generate text from OpenAI's chat completion API.
        Handles quotas, retries, trimming, and metrics.
        """
        try:
            tenant_id = get_tenant_id()
            user_id = get_user_id()
            user_role = get_user_role()

            # Trim prompt to token limit
            trimmed = trim_to_token_limit(prompt)

            # Resolve the model to use
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

            # Test mode - no API call
            if test_mode:
                logger.info("[OPENAI_GEN_TEST] Returning deterministic test output.")
                return f"[TEST MODE] Prompt length={len(trimmed)} Model={used_model}"

            # Check quota before calling API
            if not check_quota(tenant_id=tenant_id, event_type="openai_tokens"):
                raise AppError(
                    code="OPENAI_GEN_000",
                    message="Quota exceeded for tenant.",
                    details=f"Tenant={tenant_id}"
                )

            # Call OpenAI API
            start_time = time.time()
            response = await self.client.chat.completions.create(
                model=used_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": trimmed},
                ],
                temperature=temperature,
            )
            latency = time.time() - start_time
            logger.info(
                redact_log(
                    mask_phi(f"[METRIC] OpenAI latency: {latency:.2f}s for tenant={tenant_id}")
                )
            )

            # Validate response
            choices = getattr(response, "choices", [])
            if not choices or not hasattr(choices[0], "message"):
                raise AppError(
                    code="OPENAI_GEN_001",
                    message="OpenAI returned no completions.",
                    details=f"Model={used_model}, Prompt length={len(trimmed)}",
                )

            content = choices[0].message.content.strip()

            # Log usage
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
                        "role": user_role,
                        "latency": latency,
                    },
                )

            return content

        except OpenAIError as e:
            handle_error(
                e,
                code="OPENAI_GEN_002",
                user_message="OpenAI API error occurred. Please try again later.",
                raise_it=True,
            )

        except AppError:
            # Already handled in logic
            raise

        except Exception as e:
            handle_error(
                e,
                code="OPENAI_GEN_003",
                user_message="Unexpected error during text generation.",
                raise_it=True,
            )


# Singleton client instance for synchronous calls
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
    Sync wrapper for safe_generate using asyncio.run().
    Used in synchronous contexts.
    """
    return asyncio.run(
        openai_client_instance.safe_generate(
            prompt=prompt,
            model=model,
            system_msg=system_msg,
            temperature=temperature,
            test_mode=test_mode,
        )
    )
