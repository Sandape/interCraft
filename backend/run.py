"""Entry point that ensures SelectorEventLoop on Windows for psycopg."""
import platform
import sys

if platform.system() == "Windows":
    import asyncio
    import selectors

    if isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
