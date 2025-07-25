import pandas as pd
from services.openai_client import safe_generate
from core.prompts.style_transfer import build_style_transfer_prompt

def generate_style_mimic_output(example_paragraphs: list[str], new_input: str) -> str:
    prompt = build_style_transfer_prompt(example_paragraphs, new_input)
    return safe_generate(prompt, model="gpt-4", temperature=0.7)

def run_batch_style_transfer(example_paragraphs: list[str], df: pd.DataFrame, input_col: str) -> pd.DataFrame:
    outputs = []
    for i, row in df.iterrows():
        original = str(row[input_col])
        styled = generate_style_mimic_output(example_paragraphs, original)
        outputs.append({
            "Original Input": original,
            "Styled Output": styled
        })
    return pd.DataFrame(outputs)
