def build_style_transfer_prompt(example_paragraphs: list[str], new_input: str) -> str:
    """
    Build the style transfer prompt using example paragraphs and a new input text.
    Returns an empty string if either input is invalid.
    """
    if not new_input or not isinstance(new_input, str):
        return ""

    # Filter out empty examples
    cleaned_examples = [ex.strip() for ex in example_paragraphs if ex and ex.strip()]
    examples = "\n\n---\n\n".join(cleaned_examples) if cleaned_examples else "[No examples provided]"

    return f"""
You are rewriting factual inputs to match the tone, structure, and style of the provided examples.

--- Example Paragraph(s) ---
{examples}

--- New Input ---
{new_input}

--- Instruction ---
Rephrase the new input to match the same style, voice, and structure as the example(s). 
Do not copy the text. Make it sound like the same author wrote it, with a professional and persuasive legal tone.
""".strip()
