"""Judge prompts for RACE and FACT.

RACE_MERGED_SCORE_PROMPT and FACT_EXTRACT_PROMPT are ported verbatim from
DeepResearch Bench (Apache-2.0) so scores stay comparable to the leaderboard.
FACT_SUPPORT_PROMPT is authored to the metric spec in the upstream README
(Citation Accuracy = % of claims the cited source actually supports).
"""

from __future__ import annotations

# --- RACE: comparative 4-dimension report scoring (ported: score_prompt_en.py) ---
RACE_MERGED_SCORE_PROMPT = """
<system_role>You are a strict, meticulous, and objective research article evaluation expert. You excel at using specific assessment criteria to deeply compare two articles on the same task, providing precise scores and clear justifications.</system_role>

<user_prompt>
**Task Background**
There is a deep research task, and you need to evaluate two research articles written for this task. We will assess the articles across four dimensions: Comprehensiveness, Insight, Instruction Following, and Readability. The content is as follows:
<task>
"{task_prompt}"
</task>

**Articles to Evaluate**
<article_1>
"{article_1}"
</article_1>

<article_2>
"{article_2}"
</article_2>

**Evaluation Criteria**
Now, you need to evaluate and compare these two articles based on the following **evaluation criteria list**, providing comparative analysis and scoring each on a scale of 0-10. Each criterion includes an explanation, please understand carefully.

<criteria_list>
{criteria_list}
</criteria_list>

<Instruction>
**Your Task**
Please strictly evaluate and compare `<article_1>` and `<article_2>` based on **each criterion** in the `<criteria_list>`. You need to:
1.  **Analyze Each Criterion**: Consider how each article fulfills the requirements of each criterion.
2.  **Comparative Evaluation**: Analyze how the two articles perform on each criterion, referencing the content and criterion explanation.
3.  **Score Separately**: Based on your comparative analysis, score each article on each criterion (0-10 points).

**Scoring Rules**
For each criterion, score both articles on a scale of 0-10 (continuous values). The score should reflect the quality of performance on that criterion:
*   0-2 points: Very poor performance. Almost completely fails to meet the criterion requirements.
*   2-4 points: Poor performance. Minimally meets the criterion requirements with significant deficiencies.
*   4-6 points: Average performance. Basically meets the criterion requirements, neither good nor bad.
*   6-8 points: Good performance. Largely meets the criterion requirements with notable strengths.
*   8-10 points: Excellent/outstanding performance. Fully meets or exceeds the criterion requirements.

**Output Format Requirements**
Please **strictly** follow the `<output_format>` below for each criterion evaluation. **Do not include any other unrelated content, introduction, or summary**.
</Instruction>

<output_format>
{{
    "comprehensiveness": [
        {{
            "criterion": "[Text content of the criterion]",
            "analysis": "[Comparative analysis]",
            "article_1_score": 0,
            "article_2_score": 0
        }}
    ],
    "insight": [ ... ],
    "instruction_following": [ ... ],
    "readability": [ ... ]
}}
</output_format>

Now, please evaluate the two articles based on the research task and criteria. Output ONLY the JSON object, with every criterion from the criteria list scored, and ensure the JSON is parsable with special characters escaped.
</user_prompt>
"""

# --- FACT: extract (fact, ref_idx, url) triplets (ported: extract.py prompt_template_en) ---
FACT_EXTRACT_PROMPT = """You will be provided with a research report. The body of the report will contain some citations to references.

Citations in the main text may appear in the following forms:
1. A segment of text + space + number, for example: "... dividing society into 7 levels 15"
2. A segment of text + [number], for example: "... dividing society into 7 levels[15]"
3. A segment of text + [number+line/summary markers], for example: "... 7 levels[15L10][5L23][7summary]"
4. [Citation Source](Citation Link) appearing directly in the text.

Please identify **all** instances where references are cited in the main text, and extract (fact, ref_idx, url) triplets. When extracting:
1. Include enough surrounding context that each fact is complete and understandable, not just a phrase.
2. If a fact cites multiple references, emit one triplet per reference.
3. For form 3, ref_idx is only the first number. For form 4 (inline link), set ref_idx to 0.
4. If the text has no in-line citation markers (only a reference list at the end), return an empty list.

Return a JSON list; each item is a triplet:
[
    {{
        "fact": "Text segment from the report (escape quotes for valid JSON).",
        "ref_idx": "index of the cited reference",
        "url": "URL of the cited reference (from the reference list or inline link)."
    }}
]

Here is the main text of the research report:
{report_text}

Begin extraction now. Output ONLY the JSON list, no chatter or explanation."""

# --- FACT: support check (authored to README metric spec) ---
FACT_SUPPORT_PROMPT = """You are a strict fact-checking judge. Decide whether the CITED SOURCE supports the CLAIM.

<claim>
{claim}
</claim>

<cited_source_content>
{source_content}
</cited_source_content>

A claim is "supported" only if the source content directly states or clearly
entails it. If the source is unrelated, contradicts the claim, is an error
message, or is too vague to confirm, it is "not supported".

Output ONLY this JSON object:
{{"supported": true or false, "reason": "one short sentence"}}"""
