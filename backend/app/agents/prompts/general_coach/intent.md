Classify the user's question into one of these intent categories:

1. resume_optimize — Questions about resume improvement, optimization, tailoring for specific jobs
2. interview_practice — Questions about interview skills, mock interview practice, answering techniques
3. career_advice — Questions about career development, learning paths, skill building, industry trends
4. chitchat — General conversation, greetings, casual questions not fitting above categories

Examples:
- "帮我优化简历中的项目描述" → resume_optimize
- "如何准备系统设计面试" → career_advice
- "React 动画有哪些方案" → interview_practice
- "你好" → chitchat

User question: {question}

Output ONLY a JSON object:
{{"intent": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief reason>"}}
