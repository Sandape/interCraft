"""Agent module — Personal AI Agent entity and WeChat channel management.

Each InterCraft user gets exactly one Personal Agent (1:1).
The Agent owns the WeChat iLink binding lifecycle and provides a unified
read-only data access context (AgentContext) for downstream features
(REQ-053 interview intelligence, REQ-054 conversational agent).

Sub-packages:
    backend/app/channels/  — iLink protocol, connection pool, message handler
"""
