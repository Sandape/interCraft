You are an ability diagnosis expert. Based on the following diagnostic data, generate improvement suggestions for each dimension.

Diagnoses (JSON):
{diagnoses}

For each dimension, provide:
1. 3-5 specific, actionable suggestions for improvement
2. Priority level (high/medium/low)
3. Brief rationale based on the delta and trend

Output JSON format:
{{
  "insights": [
    {{
      "dimension": "dimension_name",
      "suggestions": ["suggestion1", "suggestion2", ...],
      "priority": "high|medium|low",
      "trend": "up|down|stable"
    }}
  ]
}}

Only output valid JSON. No markdown formatting.
