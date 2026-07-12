export const resumeAIKeys = {
  all: ["resume-ai"] as const,
  analyses: (resumeId: string, mode: string) => ["resume-ai", resumeId, "analyses", mode] as const,
  run: (runId: string) => ["resume-ai", "run", runId] as const,
  suggestions: (resumeId: string, analysisId: string) => ["resume-ai", resumeId, "suggestions", analysisId] as const,
  comparison: (beforeAnalysisId: string, afterAnalysisId: string) =>
    ["resume-ai", "comparison", beforeAnalysisId, afterAnalysisId] as const,
};
