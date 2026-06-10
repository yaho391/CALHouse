from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "CalHouse.Api" / "App_Data" / "calhouse.db"
EMULATOR_LOG = ROOT / "tools" / "custom_http_requests.jsonl"
API_BASE = "http://127.0.0.1:5000/api"


def request(method: str, path: str, token: str | None = None, payload: dict | None = None) -> tuple[int, object]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(f"{API_BASE}{path}", data=body, method=method.upper())
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(req, timeout=5) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text) if text else None
    except HTTPError as ex:
        text = ex.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {ex.code} {path}: {text}") from ex
    except URLError as ex:
        raise RuntimeError(f"Request failed {path}: {ex}") from ex


def read_active_admin() -> int:
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute("SELECT Id FROM Users WHERE Role = 'Admin' AND IsActive = 1 ORDER BY Id LIMIT 1").fetchone()
    if not row:
        raise RuntimeError("No active admin found")
    return int(row[0])


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest().upper()


def create_temporary_admin_session(user_id: int) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    token = secrets.token_urlsafe(32)
    hashed = token_hash(token)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            INSERT INTO UserSessions (UserId, TokenHash, CreatedAt, ExpiresAt, LastSeenAt)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, hashed, now.isoformat(), (now + timedelta(hours=2)).isoformat(), now.isoformat()),
        )
        con.commit()
    return token, hashed


def delete_temporary_session(hashed: str | None) -> None:
    if not hashed:
        return
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM UserSessions WHERE TokenHash = ?", (hashed,))
        con.commit()


def read_emulator_entries() -> list[dict[str, object]]:
    if not EMULATOR_LOG.exists():
        return []
    entries: list[dict[str, object]] = []
    for line in EMULATOR_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def wait_for_http_request(path: str, expected_state: str, seen_count: int, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        entries = read_emulator_entries()
        for entry in entries[seen_count:]:
            if entry.get("method") != "POST" or entry.get("path") != path:
                continue
            try:
                body = json.loads(str(entry.get("body") or "{}"))
            except json.JSONDecodeError:
                body = {}
            if body.get("state") == expected_state and body.get("isOn") == (expected_state == "ON"):
                return
        time.sleep(0.25)
    raise RuntimeError(f"Custom HTTP request path={path!r} state={expected_state!r} did not reach emulator")


def main() -> None:
    user_id = read_active_admin()
    token, temporary_token_hash = create_temporary_admin_session(user_id)
    device_id: int | None = None
    try:
        _, rooms = request("GET", "/rooms", token=token)
        if not rooms:
            _, room = request("POST", "/rooms", token=token, payload={"name": "Custom HTTP Test Room", "zone": "Tests"})
            room_id = int(room["id"])
        else:
            room_id = int(rooms[0]["id"])

        external_id = f"custom-http-emulator-{int(time.time())}"
        payload = {
            "name": "Custom HTTP Emulator Test",
            "roomId": room_id,
            "isOn": False,
            "type": "relay",
            "provider": "custom_http",
            "protocol": "http",
            "channel": "lan",
            "externalId": external_id,
            "manufacturer": "HTTP",
            "model": "Emulator",
            "connection": {
                "url": "http://127.0.0.1:8090/device/power/{stateLower}",
                "method": "POST",
                "headers": "{\"X-CALHouse-Test\":\"custom-http\"}",
                "body_template": "{\"state\":\"{state}\",\"isOn\":{isOn}}",
            },
        }
        _, device = request("POST", "/devices", token=token, payload=payload)
        device_id = int(device["id"])

        before = len(read_emulator_entries())
        request("PUT", f"/devices/{device_id}/toggle", token=token)
        wait_for_http_request("/device/power/on", "ON", before)

        before = len(read_emulator_entries())
        request("PUT", f"/devices/{device_id}/toggle", token=token)
        wait_for_http_request("/device/power/off", "OFF", before)

        _, final_device = request("GET", f"/devices/{device_id}", token=token)
        print(
            json.dumps(
                {
                    "ok": True,
                    "deviceId": device_id,
                    "externalId": external_id,
                    "requests": read_emulator_entries(),
                    "connectionStatus": final_device.get("connectionStatus"),
                    "connectionMessage": final_device.get("connectionMessage"),
                    "isOn": final_device.get("isOn"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        if device_id is not None:
            try:
                request("DELETE", f"/devices/{device_id}", token=token)
            except Exception:
                pass
        delete_temporary_session(temporary_token_hash)


if __name__ == "__main__":
    main()
