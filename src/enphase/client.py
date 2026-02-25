"""Real Enphase IQ Gateway client using local REST API with JWT auth."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from enphase.base import BaseEnphaseClient

log = logging.getLogger("home-hud.enphase.client")


class EnphaseClient(BaseEnphaseClient):
    """Connects to an Enphase IQ Gateway on the local network.

    Uses JWT bearer token auth against the gateway's HTTPS API.
    The gateway uses a self-signed certificate, so TLS verification is disabled.
    """

    def __init__(self, config: dict):
        import httpx

        self._config = config
        self._host = config.get("enphase_host", "192.168.1.67")
        self._base_url = f"https://{self._host}"
        db_path = config.get("solar_db_path", "data/solar.db")
        self._token_path = Path(db_path).parent / ".enphase_token"

        self._token = self._load_token(config)
        self._client = httpx.Client(
            base_url=self._base_url,
            verify=False,
            timeout=10.0,
            headers=self._auth_headers(),
        )

    def _has_credentials(self, config: dict | None = None) -> bool:
        """Check if Enlighten credentials are available for token generation."""
        cfg = config or self._config
        return bool(
            cfg.get("enphase_email")
            and cfg.get("enphase_password")
            and cfg.get("enphase_serial")
        )

    def _decode_token_expiry(self, token: str) -> datetime | None:
        """Decode JWT exp claim without a crypto library.

        JWT format is header.payload.signature — we only need the payload.
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            # base64url decode: replace URL-safe chars and add padding
            payload_b64 = parts[1].replace("-", "+").replace("_", "/")
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.b64decode(payload_b64))
            exp = payload.get("exp")
            if exp is None:
                return None
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        except Exception:
            log.debug("Could not decode JWT expiry", exc_info=True)
            return None

    def _log_token_expiry(self, token: str, source: str) -> None:
        """Log token source and expiry information."""
        expiry = self._decode_token_expiry(token)
        if expiry:
            now = datetime.now(tz=timezone.utc)
            remaining = expiry - now
            days = remaining.days
            if days < 0:
                log.warning("%s (EXPIRED %d days ago)", source, abs(days))
            elif days <= 7:
                log.warning("%s (expires in %d days — will refresh soon)", source, days)
            else:
                log.info(
                    "%s (expires %s, %d days remaining)",
                    source, expiry.strftime("%Y-%m-%d"), days,
                )
        else:
            log.info("%s (could not determine expiry)", source)

    def _token_needs_refresh(self, token: str) -> bool:
        """Return True if token is expired or within 7 days of expiry."""
        expiry = self._decode_token_expiry(token)
        if expiry is None:
            return False  # Can't determine — assume OK
        return datetime.now(tz=timezone.utc) >= expiry - timedelta(days=7)

    def _load_token(self, config: dict) -> str:
        """Load JWT token from config, cached file, or generate from credentials."""
        has_creds = self._has_credentials(config)

        # 1. Explicit token in env — always use it (user override)
        token = config.get("enphase_token", "")
        if token:
            self._save_token(token)
            self._log_token_expiry(token, "Using explicit ENPHASE_TOKEN from env")
            return token

        # 2. Cached token from file
        if self._token_path.exists():
            try:
                cached = self._token_path.read_text().strip()
                if cached:
                    if self._token_needs_refresh(cached):
                        if has_creds:
                            log.info("Cached token expiring soon, refreshing")
                            new_token = self._generate_token(
                                config["enphase_email"],
                                config["enphase_password"],
                                config["enphase_serial"],
                            )
                            if new_token:
                                self._log_token_expiry(
                                    new_token, "Generated new token via Enlighten"
                                )
                                return new_token
                            log.warning("Refresh failed, falling back to cached token")
                        else:
                            log.warning(
                                "Cached token expiring soon but no credentials "
                                "configured for refresh"
                            )
                    self._log_token_expiry(cached, "Using cached token")
                    return cached
            except OSError:
                log.warning("Could not read cached token file")

        # 3. Auto-generate from Enlighten credentials
        if has_creds:
            token = self._generate_token(
                config["enphase_email"],
                config["enphase_password"],
                config["enphase_serial"],
            )
            if token:
                self._log_token_expiry(token, "Generated new token via Enlighten")
                return token

        log.warning(
            "No Enphase token available — set ENPHASE_EMAIL + ENPHASE_PASSWORD "
            "+ ENPHASE_SERIAL for auto-auth, or set ENPHASE_TOKEN directly"
        )
        return ""

    def _generate_token(self, email: str, password: str, serial: str) -> str:
        """Generate a JWT via Enlighten login + Entrez token exchange."""
        import httpx

        try:
            # Step 1: Login to Enlighten
            log.info("Generating Enphase token via Enlighten login")
            login_resp = httpx.post(
                "https://enlighten.enphaseenergy.com/login/login.json?",
                data={"user[email]": email, "user[password]": password},
                timeout=15.0,
            )
            login_resp.raise_for_status()
            session_id = login_resp.json().get("session_id")
            if not session_id:
                log.error("Enlighten login did not return session_id")
                return ""

            # Step 2: Get token from Entrez
            token_resp = httpx.post(
                "https://entrez.enphaseenergy.com/tokens",
                json={"session_id": session_id, "serial_num": serial, "username": email},
                timeout=15.0,
            )
            token_resp.raise_for_status()
            token = token_resp.text.strip()
            if token:
                self._save_token(token)
                log.info("Successfully generated and cached Enphase token")
                return token
            log.error("Entrez returned empty token")
            return ""

        except Exception:
            log.exception("Failed to generate Enphase token")
            return ""

    def _save_token(self, token: str) -> None:
        """Cache token to file for persistence across restarts."""
        try:
            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            self._token_path.write_text(token)
        except OSError:
            log.warning("Could not cache Enphase token to %s", self._token_path)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def _refresh_token_and_retry(self) -> bool:
        """Attempt to refresh the token using stored credentials."""
        email = self._config.get("enphase_email", "")
        password = self._config.get("enphase_password", "")
        serial = self._config.get("enphase_serial", "")
        if not (email and password and serial):
            log.error("Cannot refresh token — no credentials configured")
            return False

        self._token = self._generate_token(email, password, serial)
        if self._token:
            self._client.headers.update(self._auth_headers())
            return True
        return False

    def _get(self, path: str) -> dict | list | None:
        """Make a GET request with retry on connection error and 401 refresh."""
        for attempt in range(2):
            try:
                resp = self._client.get(path)
                if resp.status_code == 401 and attempt == 0:
                    log.warning("Got 401, attempting token refresh")
                    if self._refresh_token_and_retry():
                        continue
                    return None
                resp.raise_for_status()
                return resp.json()
            except Exception:
                if attempt == 0:
                    log.warning("Request to %s failed, retrying once", path)
                    continue
                log.exception("Request to %s failed after retry", path)
                return None
        return None

    def get_production(self) -> dict:
        data = self._get("/production.json")
        if not data:
            return {
                "production_w": 0, "consumption_w": 0, "net_w": 0,
                "production_wh": 0, "consumption_wh": 0,
            }

        production = data.get("production", [{}])
        consumption = data.get("consumption", [{}])

        # production[0] is micro-inverters, production[1] is total (if EIM present)
        # consumption[0] is total consumption
        prod_entry = production[1] if len(production) > 1 else production[0] if production else {}
        cons_entry = consumption[0] if consumption else {}

        prod_w = prod_entry.get("wNow", 0)
        cons_w = cons_entry.get("wNow", 0)
        prod_wh = prod_entry.get("whToday", 0) or prod_entry.get("whLifetime", 0)
        cons_wh = cons_entry.get("whToday", 0) or cons_entry.get("whLifetime", 0)

        return {
            "production_w": round(prod_w, 1),
            "consumption_w": round(cons_w, 1),
            "net_w": round(prod_w - cons_w, 1),
            "production_wh": round(prod_wh, 1),
            "consumption_wh": round(cons_wh, 1),
        }

    def get_inverters(self) -> list[dict]:
        data = self._get("/api/v1/production/inverters")
        if not data or not isinstance(data, list):
            return []

        inverters = []
        for inv in data:
            inverters.append({
                "serial": inv.get("serialNumber", ""),
                "watts": inv.get("lastReportWatts", 0),
                "max_watts": inv.get("maxReportWatts", 0),
                "last_report": datetime.fromtimestamp(
                    inv.get("lastReportDate", 0)
                ).isoformat() if inv.get("lastReportDate") else "",
            })
        return inverters

    def check_health(self) -> bool:
        """Check gateway health via unauthenticated /info endpoint."""
        import httpx

        try:
            resp = httpx.get(
                f"{self._base_url}/info",
                verify=False,
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()
