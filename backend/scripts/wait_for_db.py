import os
import sys
import time

from sqlalchemy import create_engine, text


def main() -> int:
    database_url = str(os.getenv("DATABASE_URL", "") or "").strip()
    if not database_url:
        print("[wait_for_db] DATABASE_URL is not set", file=sys.stderr)
        return 2

    max_seconds = int(os.getenv("DB_WAIT_MAX_SECONDS", "60") or "60")
    interval_seconds = float(os.getenv("DB_WAIT_INTERVAL_SECONDS", "2") or "2")

    engine = create_engine(database_url)

    deadline = time.time() + max_seconds
    attempt = 0
    while True:
        attempt += 1
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"[wait_for_db] ok (attempt={attempt})")
            return 0
        except Exception as e:
            if time.time() >= deadline:
                print(f"[wait_for_db] timed out after {max_seconds}s: {type(e).__name__}: {e}", file=sys.stderr)
                return 1
            print(f"[wait_for_db] not ready yet (attempt={attempt}): {type(e).__name__}")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
