import unicodedata
import re

# Example excerpt from your foia_constants.py for testing
STATE_CITATIONS = {
    "Alabama": "Pursuant to the provisions of the Alabama Public Records Law, Ala. Code §§ 36-12-40, 36-12-41.",
    "Alaska": "Pursuant to the provisions of the Alaska Public Records Act, Alaska Stat. §§ 40.25.110–40.25.125, 40.25.151.",
    # ... add the rest for full test ...
}

STATE_RESPONSE_TIMES = {
    "Alabama": "We expect an acknowledgment within 10 business days and a full response within 15 business days pursuant to the Alabama Open Records Act. (Agencies may extend in 15-day increments with written notice.)",
    "Alaska": "I look forward to receiving your written response within 10 working days (i.e. business days) pursuant to the Alaska Public Records Act. (Alaska allows a one-time extension of up to 10 additional working days in unusual circumstances.)",
    # ... add the rest for full test ...
}

def sanitize_for_docx(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize('NFKD', text)
    cleaned = "".join(ch for ch in normalized if unicodedata.category(ch)[0] != 'C')
    cleaned = cleaned.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("’", "'")
    return cleaned

def find_problem_chars(text: str):
    # Find control characters or suspicious unicode
    problem_chars = []
    for i, ch in enumerate(text):
        cat = unicodedata.category(ch)
        if cat[0] == 'C':  # Control characters
            problem_chars.append((i, ch, f"Control char (category {cat})"))
        elif ord(ch) > 127:
            problem_chars.append((i, ch, f"Non-ASCII char (U+{ord(ch):04X})"))
    return problem_chars

def test_foia_constants():
    for state in STATE_CITATIONS.keys():
        citation = STATE_CITATIONS[state]
        response_time = STATE_RESPONSE_TIMES.get(state, "")

        print(f"\n=== {state} ===")

        # Raw
        print("Raw state_citation:", citation)
        print("Raw state_response_time:", response_time)

        # Sanitized
        citation_clean = sanitize_for_docx(citation)
        response_clean = sanitize_for_docx(response_time)
        print("Cleaned state_citation:", citation_clean)
        print("Cleaned state_response_time:", response_clean)

        # Find problems
        problems_citation = find_problem_chars(citation)
        problems_response = find_problem_chars(response_time)

        if problems_citation:
            print("Problem chars in state_citation:")
            for pos, ch, desc in problems_citation:
                print(f"  Pos {pos}: '{ch}' - {desc}")
        else:
            print("No problem chars in state_citation.")

        if problems_response:
            print("Problem chars in state_response_time:")
            for pos, ch, desc in problems_response:
                print(f"  Pos {pos}: '{ch}' - {desc}")
        else:
            print("No problem chars in state_response_time.")

if __name__ == "__main__":
    test_foia_constants()
