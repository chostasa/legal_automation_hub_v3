# Core instructions for FOIA bullet points and synopsis generation

FOIA_BULLET_POINTS_PROMPT_TEMPLATE = """
You are drafting FOIA bullet points for a civil legal claim.

Case synopsis:
{case_synopsis}

Case type: {case_type}
Facility or system involved: {facility}
Defendant role: {defendant_role}

Explicit instructions:
{explicit_instructions}

Common requests or priorities:
{potential_requests}

Please return a detailed and **role-specific** list of records, documents, media, and internal communications that a skilled civil attorney would request from this type of facility or entity. 
Only include items that would reasonably be within the possession, custody, or control of a {defendant_role} operating within a {facility}. Do not include irrelevant medical, financial, or third-party institutional records if they would not be held by this entity.

Format output as Word-style bullet points using asterisks (*).
Only return the list.
"""

FOIA_SYNOPSIS_PROMPT = """
Summarize the following legal case background in 2 professional sentences explaining what happened and the resulting harm or damages. Do not include any parties' names or personal identifiers:

{case_synopsis}
"""
