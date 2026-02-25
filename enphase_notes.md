# Enphase Envoy Local API Reference

## Device Info

- **Model**: Enphase Envoy (IQ Gateway)
- **Part Number**: 800-00555-r03
- **Serial Number**:
- **Firmware**: D8.3.5286
- **Local IP**: 192.168.1.67
- **Auth Method**: JWT token (web-tokens enabled)

## Authentication

The Envoy requires a JWT Bearer token for all local API access. Tokens are valid for **1 year** for system owners.

### Token Generation (2-step process)

**Step 1: Get session ID from Enlighten**

```
POST https://enlighten.enphaseenergy.com/login/login.json?
Content-Type: multipart/form-data

Fields:
  user[email] = <enphase_email>
  user[password] = <enphase_password>

Response: JSON with "session_id" field
```

**Step 2: Get JWT token from Entrez**

```
POST https://entrez.enphaseenergy.com/tokens
Content-Type: application/json

Body: {
  "session_id": "<session_id_from_step_1>",
  "serial_num": "122117051926",
  "username": "<enphase_email>"
}

Response: Raw JWT token string (not JSON-wrapped)
```

### Using the Token

All local API requests must:
- Use **HTTPS** (not HTTP) — the Envoy does not respond on port 80
- Include `-k` or equivalent to skip SSL verification (self-signed cert)
- Include the header: `Authorization: Bearer <token>`

## Available Local API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/info` | GET | Device info (XML, no auth required) |
| `/production.json` | GET | Current production/consumption summary |
| `/production.json?details=1` | GET | Detailed production with per-phase data |
| `/api/v1/production` | GET | Production data |
| `/api/v1/production/inverters` | GET | Per-panel microinverter data (updates every 5 min) |
| `/inventory.json` | GET | Inventory of all connected devices |
| `/home.json` | GET | Home overview data |

## Example curl

```bash
curl -k -H "Authorization: Bearer $TOKEN" https://192.168.1.67/production.json
```

## Key Notes

- The `/info` endpoint is unauthenticated and returns XML — useful for health checks.
- All other endpoints require the JWT Bearer token.
- The Envoy uses a **self-signed SSL certificate** — any HTTP client must be configured to skip TLS verification for this host.
- Inverter-level data (`/api/v1/production/inverters`) only updates once every 5 minutes.
- Token should be stored securely and reused; regenerate annually or on auth failure (401).
- Base URL: `https://192.168.1.67`