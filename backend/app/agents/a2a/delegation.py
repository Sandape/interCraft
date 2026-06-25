"""Delegation runner for the A2A framework (REQ-031 US1, T012).

``DelegationRunner`` executes one delegation: call the agent's async
function with timeout, retry once on failure, persist the outcome to
``a2a_messages`` if a repository is supplied.

Spec mapping (FR-006, FR-008, FR-009):

- **Timeout** (FR-006): ``asyncio.wait_for(agent_fn(context), timeout=...)``.
- **Failure handling** (FR-008): retry once on non-timeout exception;
  second failure escalates to ``status="failed"`` with ``error_reason``.
- **Output validation** (FR-009): skipped at this layer — the
  Supervisor wraps the agent function with Pydantic validation before
  calling it.

Why no retry on timeout?
    A timeout means the agent's LLM/IO didn't return in time. Retrying
    once is unlikely to succeed (the same load probably persists), and
    it consumes the user's quota. US1 ships retry-once only for
    *failures*; circuit breaker ⏳ (US3).
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable
from uuid import UUID

import structlog

from app.agents.a2a.repository import A2AMessageRepository
from app.agents.a2a.schemas import A2AMessage, A2AMessageStatus, DelegationRecord

logger = structlog.get_logger("agents.a2a.delegation")


class AgentTimeoutError(Exception):
    """Raised by :class:`DelegationRunner` when an agent exceeds its timeout."""

    def __init__(self, agent_name: str, timeout_seconds: float) -> None:
        self.agent_name = agent_name
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Agent {agent_name!r} timed out after {timeout_seconds}s"
        )


AgentFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class DelegationRunner:
    """Runs one delegation with timeout + retry-once + optional persistence."""

    def __init__(self, *, repository: A2AMessageRepository | None = None) -> None:
        self._repository = repository

    async def run(
        self,
        *,
        parent: str,
        child: str,
        task: str,
        context: dict[str, Any],
        agent_fn: AgentFn,
        timeout_seconds: float,
        trace_id: str,
        thread_id: str,
        expected_output: dict[str, Any] | None = None,
    ) -> DelegationRecord:
        """Execute one delegation.

        Parameters
        ----------
        parent:
            Name of the delegating agent (or ``__supervisor__``).
        child:
            Name of the target agent (looked up by the caller).
        task:
            Short description of the subtask.
        context:
            The state slice passed to the agent's function.
        agent_fn:
            Async callable ``(context) -> dict``. The Supervisor
            constructs this from the registered
            :class:`~app.agents.a2a.AgentDefinition`.
        timeout_seconds:
            Wall-clock budget. The runner uses ``asyncio.wait_for``
            so a hanging agent doesn't block the graph indefinitely.
        trace_id:
            OTel trace_id (or request_id fallback) — persisted on the
            A2AMessage for cross-graph correlation.
        thread_id:
            LangGraph thread_id — persisted for per-session queries.
        expected_output:
            Optional description of the expected output shape. Stored
            on the A2AMessage for later schema validation
            (deferred to US4).

        Returns
        -------
        DelegationRecord
            In-memory record. The DB row (if persisted) carries the
            same fields plus timestamps and a UUID.
        """
        start = time.time()
        retry_count = 0
        result: dict[str, Any] | None = None
        error_reason: str | None = None
        terminal_status: A2AMessageStatus = A2AMessageStatus.PENDING
        message_id: UUID | None = None

        # Create the pending row up front so the caller can correlate
        # by id even if the runner crashes mid-delegation.
        if self._repository is not None:
            try:
                row = await self._repository.create(
                    trace_id=trace_id,
                    thread_id=thread_id,
                    parent_agent=parent,
                    child_agent=child,
                    task=task,
                    context=context,
                    expected_output=expected_output or {},
                    status=A2AMessageStatus.PENDING,
                )
                message_id = row.id
            except Exception:
                logger.warning(
                    "a2a.delegation_persist_failed",
                    stage="create",
                    parent=parent,
                    child=child,
                    exc_info=True,
                )

        logger.info(
            "a2a.delegation_started",
            parent=parent,
            child=child,
            task=task,
            timeout_seconds=timeout_seconds,
            trace_id=trace_id,
            thread_id=thread_id,
        )

        try:
            result = await asyncio.wait_for(agent_fn(context), timeout=timeout_seconds)
            terminal_status = A2AMessageStatus.SUCCESS
            logger.info(
                "a2a.delegation_succeeded",
                parent=parent,
                child=child,
                task=task,
                retry_count=retry_count,
                duration_ms=int((time.time() - start) * 1000),
            )
        except asyncio.TimeoutError as exc:
            terminal_status = A2AMessageStatus.TIMEOUT
            error_reason = f"Timeout after {timeout_seconds}s"
            logger.warning(
                "a2a.delegation_timeout",
                parent=parent,
                child=child,
                task=task,
                timeout_seconds=timeout_seconds,
                exc_info=False,
            )
            # Don't retry on timeout — same load probably persists.
        except Exception as exc:
            # First failure: retry once.
            retry_count = 1
            logger.warning(
                "a2a.delegation_retry",
                parent=parent,
                child=child,
                task=task,
                attempt=2,
                error=str(exc),
                exc_info=True,
            )
            try:
                result = await asyncio.wait_for(agent_fn(context), timeout=timeout_seconds)
                terminal_status = A2AMessageStatus.SUCCESS
                logger.info(
                    "a2a.delegation_succeeded_after_retry",
                    parent=parent,
                    child=child,
                    task=task,
                    retry_count=retry_count,
                    duration_ms=int((time.time() - start) * 1000),
                )
            except asyncio.TimeoutError as exc2:
                terminal_status = A2AMessageStatus.TIMEOUT
                error_reason = f"Timeout after retry: {timeout_seconds}s"
                logger.warning(
                    "a2a.delegation_timeout",
                    parent=parent,
                    child=child,
                    task=task,
                    timeout_seconds=timeout_seconds,
                    retry_count=retry_count,
                )
            except Exception as exc2:
                terminal_status = A2AMessageStatus.FAILED
                error_reason = f"{type(exc2).__name__}: {exc2}"
                logger.error(
                    "a2a.delegation_failed",
                    parent=parent,
                    child=child,
                    task=task,
                    retry_count=retry_count,
                    error=error_reason,
                    exc_info=True,
                )

        duration_ms = int((time.time() - start) * 1000)

        # Persist the terminal status.
        if self._repository is not None and message_id is not None:
            try:
                await self._repository.update_status(
                    message_id,
                    status=terminal_status,
                    result=result,
                    error_reason=error_reason,
                    duration_ms=duration_ms,
                    retry_count=retry_count,
                )
            except Exception:
                logger.warning(
                    "a2a.delegation_persist_failed",
                    stage="update_status",
                    message_id=str(message_id),
                    parent=parent,
                    child=child,
                    exc_info=True,
                )

        return DelegationRecord(
            parent=parent,
            child=child,
            task=task,
            result=result,
            duration_ms=duration_ms,
            status=terminal_status,
            retry_count=retry_count,
            error_reason=error_reason,
        )


__all__ = ["AgentFn", "AgentTimeoutError", "DelegationRunner"]