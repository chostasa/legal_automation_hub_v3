NO_HALLUCINATION_NOTE = """
Do not fabricate or assume any facts. Use only the information provided. Avoid adding details that are not explicitly stated. 
Do not add headings, greetings, or signoffs — the template controls those. 
Refer to the client by their first name only. Maintain consistent names, pronouns, and chronology. 
Do not describe more than one version of the incident. 
Do not repeat injury or treatment details across sections unless required for context.
"""

STRUCTURE_GUIDE_NOTE = """
Follow this sequence exactly:
1. Introduce the defendant’s duty of care.
2. Establish the breach of duty with specifics.
3. Link the breach directly to the harm (causation).
4. Detail the full harm once: physical, emotional, and economic.
5. Conclude with a firm settlement demand that ties the requested amount directly to quantified damages.

Each section must build on the prior and avoid repeating full injury descriptions. Use linking transitions between sections.
"""

LEGAL_FLUENCY_NOTE = """
Write in the tone and clarity of a senior trial attorney. 
Frame facts persuasively using the negligence framework (duty, breach, causation, harm). 
Be assertive, precise, and polished. Avoid vague or filler language. 
Clearly explain why the defendant is liable using direct causation language. 
Quantify damages explicitly: mention past medical expenses, projected costs, lost wages, and pain & suffering separately if possible. 
After fully describing injuries once, refer back to them only by category (e.g., orthopedic trauma, neurological harm, loss of normal life).
Reference corroborating evidence (police reports, witnesses, footage) only once for maximum impact.
"""

LEGAL_TRANSITION_NOTE = """
Use confident legal transitions to connect facts and conclusions, such as:
- “This breach of duty directly caused...”
- “Accordingly, liability is established under...”
- “Based on these facts, recovery is warranted under...”
- “These injuries have profoundly disrupted...”

Avoid tentative or apologetic language.
"""

NO_PASSIVE_LANGUAGE_NOTE = """
Use active voice exclusively. Eliminate all passive constructions. 
Example: Do not write “Jane was struck by the snowplow.” 
Write “The snowplow struck Jane.”
"""

BAN_PHRASES_NOTE = """
Do not use speculative or weak words: “may,” “might,” “potential,” “appears to,” “possibly,” “believes that.” 
Replace them with confident terms: “is,” “will show,” “demonstrates,” “establishes.”
"""

FINAL_POLISH_NOTE = """
Each paragraph must advance the legal theory or damages claim. 
Do not repeat the same injury, fact, or legal point in multiple sections. If it has been stated once in detail, summarize or reference it later by category (e.g., "orthopedic trauma") instead of repeating the full description.

Be concise and persuasive: cut technical or clinical detail (e.g., imaging results, medication names) unless it strengthens causation or damages. 

Vary sentence length and structure for maximum impact. 
Close with a settlement demand paragraph that ties the damages to the requested amount in a single, tight conclusion.
"""

FULL_SAFETY_PROMPT = "\n\n".join([
    NO_HALLUCINATION_NOTE,
    LEGAL_FLUENCY_NOTE,
    STRUCTURE_GUIDE_NOTE,
    LEGAL_TRANSITION_NOTE,
    NO_PASSIVE_LANGUAGE_NOTE,
    BAN_PHRASES_NOTE,
    FINAL_POLISH_NOTE
])
