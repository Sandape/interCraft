# 038 - LLM Structured Output Hardening

**Status**: active / draft
**Spec**: [spec.md](./spec.md)
**Created**: 2026-07-02

## Current-System Assessment

The current implementation has partial resilience, but it is not a strict structured-output design.

Observed patterns:

- `backend/app/agents/llm_client.py` wraps the raw OpenAI-compatible client and returns `content: str`; it has retries, quota accounting, metrics, and AI invocation summaries, but no structured schema parameter or typed response path.
- Multiple machine-consumed nodes ask the model to "return JSON", then extract a JSON-looking substring with regex and call `json.loads`.
- `planner_generate` is the strongest current example because it validates the parsed dict into `InterviewPlan`, but the LLM is still asked for raw text first and the parser remains tolerant rather than contract-first.
- `score`, `report`, `question_gen`, `intake`, `error_coach.evaluate`, `general_coach.intent`, `resume_optimize.suggest_blocks`, and `ability_diagnose.generate_insight` all have prompt-only JSON discipline plus local best-effort parsing or fallback behavior.
- A2A `AgentDefinition` already declares `input_schema` and `output_schema`, but current framework comments show output validation is deferred rather than enforced at the Supervisor boundary.
- Existing eval coverage checks Chinese fidelity and several graph behaviors, but malformed structured-output handling is not yet a first-class regression target.

Conclusion: the system is fault-tolerant in the "do not crash" sense, but not robust in the "reject invalid model data before it becomes Agent state" sense.

## Source-Checked Best Practice

LangChain/LangGraph's current structured-output guidance favors schema-first model calls instead of prompt-only JSON. The key pattern is to bind a schema to the model call and receive a validated structured result.

Official references:

- LangChain structured output docs: [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- LangChain chat model API: [`with_structured_output`](https://reference.langchain.com/python/langchain-core/language_models/chat_models/BaseChatModel/#langchain_core.language_models.chat_models.BaseChatModel.with_structured_output)
- LangGraph agent response format docs: [`create_agent` / structured response](https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent/)
- OpenAI official guide: [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- DeepSeek official guide: [JSON Output](https://api-docs.deepseek.com/guides/json_mode)
- DeepSeek official guide: [Function Calling](https://api-docs.deepseek.com/guides/function_calling)

Important implications for this project:

- Pydantic schemas should become the contract for machine-consumed Agent outputs.
- LangGraph nodes should call a structured invocation path, ideally through a chat model wrapper that supports `with_structured_output(<PydanticModel>)`.
- Provider-native schema enforcement is preferred when available. If a provider path only guarantees valid JSON rather than schema adherence, the project still needs local Pydantic validation before state updates.
- Prompt text like "only output valid JSON" is useful as an instruction, but it is not a sufficient safety boundary.

## Gap Summary

| Area | Current State | Required Direction |
|---|---|---|
| LLM client | Returns raw strings from `invoke()` | Add a typed structured invocation path with schema, validation, failure category, and fallback handling |
| Output contracts | Only `InterviewPlan` is modeled in detail | Define Pydantic contracts for all machine-consumed LLM outputs |
| Parsing | Regex + `json.loads` in several nodes | Replace authoritative free-text parsing with schema-bound model calls and validation |
| Fallbacks | Mostly silent defaults | Typed, observable fallback decisions with schema failure context |
| A2A | Schema fields declared but not enforced | Enforce delegated input/output contracts at Agent boundaries |
| Tests | Golden evals focus on fidelity and expected content | Add malformed-output and contract-violation cases per Agent domain |
| Observability | LLM success/failure captured, but schema status absent | Record contract name/version, validation status, errors, and fallback usage |

## Proposed Migration Slices

1. Establish the shared structured-output layer.
   - Add a structured invocation API next to the existing raw text API.
   - Preserve quota, retry, prompt fingerprint, cost, trace, and payload capture behavior.
   - Return either a validated model instance or a typed structured-output failure.

2. Define output contracts for highest-risk nodes.
   - Interview: intake, question generation, scoring, final report, planner plan.
   - Error Coach: answer evaluation.
   - General Coach: intent classification.
   - Resume Optimize: gap analysis and patch suggestions.
   - Ability Diagnose: insight generation.

3. Migrate nodes incrementally.
   - Start with routing/scoring/patch-producing nodes because invalid data there changes business logic.
   - Keep free-form user-facing response nodes on raw text unless their output is later consumed by logic.

4. Enforce A2A boundaries.
   - Validate `input_schema` before handler execution where provided.
   - Validate `output_schema` before merging delegated results into graph state.
   - Persist schema validation failures in `a2a_messages`.

5. Expand tests and evals.
   - Add unit tests for each Pydantic output contract.
   - Add node tests for malformed output, missing fields, invalid enums, out-of-range values, extra fields, and fallback.
   - Add eval fixtures for structured-output regression cases.
   - Add a local registry check that fails when a structured node lacks a contract.

## Open Planning Notes

- The project currently depends on `langgraph`, `openai`, and Pydantic, but not an explicit chat model integration package. Planning should decide whether to add the minimal LangChain provider package required for `with_structured_output`, or to implement provider-native structured output first and wrap it behind the same project API.
- DeepSeek JSON mode should not be treated as schema adherence by itself. Local Pydantic validation remains required.
- Existing mock clients must be upgraded with the same public structured API so E2E and eval suites stay deterministic.
