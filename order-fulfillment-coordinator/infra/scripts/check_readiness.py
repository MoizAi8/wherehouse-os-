"""Require production dependencies, not just a 200 or a substring match."""
import json
import sys
import urllib.request


def is_ready(data: object) -> bool:
    if not isinstance(data, dict) or data.get("status") != "ok":
        return False
    backends = data.get("backends")
    return isinstance(backends, dict) and all(
        backends.get(name) is True for name in ("postgres", "celery", "qdrant")
    )


if __name__ == "__main__":
    try:
        with urllib.request.urlopen(sys.argv[1], timeout=8) as response:
            ready = response.status == 200 and is_ready(json.load(response))
    except Exception:
        ready = False
    sys.exit(0 if ready else 1)
