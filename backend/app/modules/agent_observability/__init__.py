"""REQ-035 agent observability package."""

__all__ = ["eval_center_router", "router"]


def __getattr__(name: str):
    if name in __all__:
        from app.modules.agent_observability.api import eval_center_router, router

        return {"eval_center_router": eval_center_router, "router": router}[name]
    raise AttributeError(name)
