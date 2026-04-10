"""Authentication for the telemetry dashboard.

Supports two enrollment paths:
- Pairing code: Pi generates a 6-digit code, user enters it in browser.
- Tailscale identity: auto-registered via tailscaled WhoIs API (Phase 6).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger("home-hud.telemetry.auth")


class AuthManager:
    """Token-based authentication with pairing code enrollment."""

    def __init__(
        self,
        secret: str | None = None,
        data_dir: str | Path = "data",
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._users_path = self._data_dir / "auth.json"
        self._lock = threading.Lock()

        # HMAC secret for token signing
        if secret:
            self._secret = secret.encode()
        else:
            self._secret = self._load_or_generate_secret()

        # Active pairing codes: {code: (user_id, expires_at)}
        self._pairing_codes: dict[str, tuple[str, float]] = {}

        # Registered users: {user_id: {name, source, created_at}}
        self._users = self._load_users()

    def _load_or_generate_secret(self) -> bytes:
        """Load secret from file or generate a new one."""
        secret_path = self._data_dir / ".auth_secret"
        if secret_path.exists():
            return secret_path.read_bytes().strip()
        secret = secrets.token_bytes(32)
        try:
            secret_path.write_bytes(secret)
            secret_path.chmod(0o600)
        except OSError:
            log.warning("Could not persist auth secret to disk")
        return secret

    def _load_users(self) -> dict:
        if self._users_path.exists():
            try:
                return json.loads(self._users_path.read_text())
            except (json.JSONDecodeError, OSError):
                log.warning("Could not load auth users file")
        return {}

    def _save_users(self) -> None:
        try:
            self._users_path.write_text(json.dumps(self._users, indent=2))
        except OSError:
            log.warning("Could not save auth users file")

    # --- Pairing code flow ---

    def generate_pairing_code(self, ttl: int = 300) -> str:
        """Generate a 6-digit pairing code valid for ttl seconds."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        user_id = str(uuid.uuid4())
        with self._lock:
            # Clean expired codes
            now = time.time()
            self._pairing_codes = {
                c: v for c, v in self._pairing_codes.items()
                if v[1] > now
            }
            self._pairing_codes[code] = (user_id, now + ttl)
        log.info("Pairing code generated: %s (expires in %ds)", code, ttl)
        return code

    def verify_pairing_code(self, code: str) -> str | None:
        """Verify a pairing code. Returns user_id on success, None on failure."""
        with self._lock:
            entry = self._pairing_codes.pop(code, None)
            if entry is None:
                return None
            user_id, expires_at = entry
            if time.time() > expires_at:
                return None
            # Register the user (first user becomes admin)
            is_first = len(self._users) == 0
            self._users[user_id] = {
                "source": "pairing",
                "admin": is_first,
                "created_at": time.time(),
            }
            self._save_users()
        log.info("User paired successfully: %s", user_id)
        return user_id

    # --- Token management ---

    def is_admin(self, user_id: str) -> bool:
        """Check if a user has admin privileges."""
        if user_id in ("localhost", "anonymous"):
            return True
        user = self._users.get(user_id)
        return bool(user and user.get("admin"))

    def create_token(self, user_id: str, source: str = "pairing") -> str:
        """Create an HMAC-signed token for the given user."""
        payload = json.dumps({
            "uid": user_id,
            "src": source,
            "adm": self.is_admin(user_id),
            "iat": int(time.time()),
        }, separators=(",", ":"))
        payload_b64 = base64.urlsafe_b64encode(
            payload.encode(),
        ).rstrip(b"=").decode()
        sig = hmac.new(
            self._secret, payload_b64.encode(), hashlib.sha256,
        ).hexdigest()[:32]
        return f"{payload_b64}.{sig}"

    def verify_token(self, token: str) -> dict | None:
        """Verify a token. Returns payload dict or None."""
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected = hmac.new(
            self._secret, payload_b64.encode(), hashlib.sha256,
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        # Decode payload
        try:
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        except (json.JSONDecodeError, ValueError):
            return None
        return payload

    # --- Tailscale identity (stub for Phase 6) ---

    def check_tailscale_identity(self, ip: str) -> str | None:
        """Check if an IP belongs to a Tailscale user via tailscaled API.

        Queries the local Tailscale daemon over its Unix socket to identify
        the user behind a Tailscale IP address.  Auto-registers new users.

        Returns user_id if identified, None otherwise.
        """
        import http.client
        import socket

        sock_path = "/var/run/tailscale/tailscaled.sock"
        try:
            # Connect to tailscaled Unix socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect(sock_path)
            conn = http.client.HTTPConnection("local-tailscaled.sock")
            conn.sock = sock

            conn.request("GET", f"/localapi/v0/whois?addr={ip}:0")
            resp = conn.getresponse()
            if resp.status != 200:
                return None

            data = json.loads(resp.read())
            login_name = (
                data.get("UserProfile", {}).get("LoginName")
                or data.get("UserProfile", {}).get("DisplayName")
                or f"tailscale-{ip}"
            )

            # Use a stable user_id derived from the Tailscale user ID
            ts_user_id = str(data.get("UserProfile", {}).get("ID", ip))
            stable_id = f"ts-{ts_user_id}"

            # Auto-register if new (first user becomes admin)
            with self._lock:
                if stable_id not in self._users:
                    is_first = len(self._users) == 0
                    self._users[stable_id] = {
                        "name": login_name,
                        "source": "tailscale",
                        "admin": is_first,
                        "created_at": time.time(),
                    }
                    self._save_users()
                    log.info(
                        "Auto-registered Tailscale user: %s (%s, admin=%s)",
                        login_name, stable_id, is_first,
                    )

            return stable_id
        except (OSError, ConnectionError, json.JSONDecodeError):
            return None
        finally:
            try:
                sock.close()
            except Exception:
                pass

    # --- User management ---

    def get_user(self, user_id: str) -> dict | None:
        return self._users.get(user_id)

    def is_registered(self, user_id: str) -> bool:
        return user_id in self._users
