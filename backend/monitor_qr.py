"""Monitor iLink QR status — polls directly, shows every response."""
import asyncio, time, json, sys
sys.path.insert(0, ".")
from app.channels.ilink_client import ILinkClient

QRCODE = sys.argv[1] if len(sys.argv) > 1 else None

async def main():
    if not QRCODE:
        print("Usage: python monitor_qr.py <qrcode_token>")
        return

    print(f"Monitoring QR: {QRCODE}")
    print("Polling iLink status — each poll holds ~30s (long-poll).")
    print("Scan the QR code now. When confirmed, this will detect it.\n")

    deadline = time.monotonic() + 300
    poll_num = 0
    while time.monotonic() < deadline:
        poll_num += 1
        t0 = time.monotonic()
        client = ILinkClient()
        await client.start()
        try:
            data = await client.get_qrcode_status(QRCODE)
            elapsed = time.monotonic() - t0
            status = data.get("status", "?")
            print(f"[#{poll_num} {time.strftime('%H:%M:%S')}] {elapsed:.0f}s → status={status}")
            if "bot_token" in data:
                print(f"  bot_token present: {bool(data.get('bot_token'))}")

            if status == "confirmed":
                print("\n✅ CONFIRMED! Binding should proceed.")
                print(f"Full response: {json.dumps(data, indent=2)}")
                break
            if status == "expired":
                print("\n❌ QR expired")
                break
        except Exception as e:
            elapsed = time.monotonic() - t0
            print(f"[#{poll_num} {time.strftime('%H:%M:%S')}] Error ({elapsed:.0f}s): {e}")
            await asyncio.sleep(3)
        finally:
            await client.stop()

    print("\nDone.")

asyncio.run(main())
