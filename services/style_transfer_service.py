import pandas as pd
from services.openai_client import safe_generate
from core.prompts.prompt_factory import build_prompt
from core.security import sanitize_text, mask_phi, redact_log
from core.error_handling import handle_error
from core.cache_utils import get_cache, set_cache
from logger import logger


def generate_style_mimic_output(example_paragraphs: list[str], new_input: str, test_mode: bool = False) -> str:
    """
    Generate a style-mimicked version of the input using example paragraphs.
    Includes input sanitization, caching, error handling, and test hooks.
    """
    try:
        if not new_input or not new_input.strip():
            raise ValueError("Input text for style transfer is empty.")

        # Join and sanitize example paragraphs
        example_text = "\n---\n".join([sanitize_text(p) for p in example_paragraphs if p.strip()])
        if not example_text:
            raise ValueError("No valid example paragraphs provided for style transfer.")

        # Build prompt using centralized prompt factory
        prompt = build_prompt(
            prompt_type="style_transfer",
            section="Style Rewriting",
            summary=sanitize_text(new_input),
            client_name="",
            example=example_text
        )

        # Use fingerprint for caching (to avoid duplicate GPT calls)
        fingerprint = f"style::{hash(example_text)}::{hash(new_input.strip())}"
        cached = get_cache(fingerprint)
        if cached:
            logger.info(f"[STYLE_CACHE_HIT] Using cached result for {fingerprint}")
            return cached

        # === Test mode hook for Phase 5 unit tests ===
        if test_mode:
            logger.info(f"[STYLE_TEST_MODE] Returning mocked output for {fingerprint}")
            return f"[MOCKED_STYLE] {new_input}"

        styled_output = safe_generate(prompt, model="gpt-4", temperature=0.7)

        if not styled_output.strip():
            raise ValueError("OpenAI returned an empty style transfer output.")

        set_cache(fingerprint, styled_output)
        return styled_output

    except Exception as e:
        return handle_error(
            e,
            code="STYLE_GEN_001",
            user_message="Failed to generate styled output. Please check inputs and try again.",
            raise_it=False
        )


def run_batch_style_transfer(example_paragraphs: list[str], df: pd.DataFrame, input_col: str, test_mode: bool = False) -> pd.DataFrame:
    """
    Run style mimic generation for all rows in the dataframe.
    Includes row-level error handling so one bad row doesn't kill the entire batch.
    Adds test hooks for Phase 5 coverage.
    """
    outputs = []
    try:
        if input_col not in df.columns:
            raise ValueError(f"Column '{input_col}' not found in input DataFrame.")

        for idx, row in df.iterrows():
            original = str(row.get(input_col, "")).strip()
            if not original:
                outputs.append({
                    "Original Input": "",
                    "Styled Output": "❌ No input text provided."
                })
                continue

            try:
                styled = generate_style_mimic_output(example_paragraphs, original, test_mode=test_mode)
                outputs.append({
                    "Original Input": original,
                    "Styled Output": styled
                })
            except Exception as row_err:
                handle_error(
                    row_err,
                    code="STYLE_BATCH_ROW_001",
                    user_message=f"Failed to process row {idx}.",
                    raise_it=False
                )
                outputs.append({
                    "Original Input": original,
                    "Styled Output": f"❌ Error processing row {idx}"
                })

        return pd.DataFrame(outputs)

    except Exception as e:
        handle_error(
            e,
            code="STYLE_BATCH_001",
            user_message="Failed to run style transfer batch process.",
            raise_it=True
        )
