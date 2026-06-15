"""Windows-safe uvicorn launcher.

uvicorn.run() doesn't accept a loop_factory on this version, so we build
the Config and Server manually and call Server.serve() inside our own
asyncio.run() with an explicit loop_factory. On Windows this guarantees
the request loop is a SelectorEventLoop, which psycopg (used by
langgraph-checkpoint-postgres) requires.
"""
import asyncio
import platform
import sys


def _selector_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()


if __name__ == "__main__":
    import uvicorn
    from uvicorn import Config, Server

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    config = Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        loop="asyncio",
        log_level="info",
    )
    server = Server(config=config)

    if platform.system() == "Windows":
        asyncio.run(server.serve(), loop_factory=_selector_loop_factory)
    else:
        asyncio.run(server.serve())