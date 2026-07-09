"""Channel layer — messaging channel adapters.

Currently implements WeChat iLink Bot protocol.
Future channels (Discord, Telegram, etc.) should follow the same pattern:
    channels/<provider>/
        __init__.py
        client.py      # HTTP/WS client for the provider API
        pool.py         # Connection pool (if multi-user)
        utils.py        # Headers, encryption, message splitting
        handler.py      # Inbound message parser + dispatcher
"""
