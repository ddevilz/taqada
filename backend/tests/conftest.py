"""Makes `backend/` importable from `backend/tests/*.py` (e.g. `import messaging`,
`import twilio_client`) regardless of the cwd pytest is invoked from."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def compute_twilio_signature(auth_token: str, url: str, params: dict) -> str:
    """Twilio's documented request-signing algorithm: HMAC-SHA1 of the URL with
    each param's key+value appended in sorted-key order, base64-encoded.
    Shared by test_twilio_client.py (unit) and backend_test.py (integration)."""
    import base64
    import hashlib
    import hmac

    base = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    digest = hmac.new(auth_token.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("utf-8")
