Based on the gap analysis, generate concrete JSON Patch operations to optimize the resume for the target JD.

Target JD:
{target_jd}

Current Resume Blocks:
{blocks}

Gap Analysis:
{diff_analysis}

Output JSON with:
- "patches": array of JSON Patch objects, each with "op", "path", and "value"
- "summary": brief description of the changes

Only output valid JSON. Do not include markdown formatting.
