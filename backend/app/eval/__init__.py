"""Eval library for feature 026 — Agent Eval-Driven Self-Improvement Loop.

Self-contained library (Constitution Principle I: Library-First). No FastAPI /
DB / LangGraph runtime dependency. Only depends on stdlib + the graph node
functions under test (which are invoked via patched LLM client).

Public API:
    ChineseFidelityChecker / ChineseFidelityResult — language fidelity gate
    GoldenCase / load_golden_cases — golden dataset loader
    EvalRunner / CaseResult / EvalReport — eval suite runner + report
"""
from app.eval.checker import ChineseFidelityChecker, ChineseFidelityResult
from app.eval.golden_loader import GoldenCase, load_golden_cases
from app.eval.runner import CaseResult, EvalReport, EvalRunner

__all__ = [
    "CaseResult",
    "ChineseFidelityChecker",
    "ChineseFidelityResult",
    "EvalReport",
    "EvalRunner",
    "GoldenCase",
    "load_golden_cases",
]
