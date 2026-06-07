from __future__ import annotations

import json
import hashlib
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "CalHouse.Api" / "App_Data" / "calhouse.db"
EMULATOR_LOG = ROOT / "tools" / "tasmota_emulator_requests.jsonl"
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


def read_admin_credentials() -> tuple[int, str, str | None]:
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            "SELECT Id, Login, PasswordPlainText FROM Users WHERE Role = 'Admin' AND IsActive = 1 ORDER BY Id LIMIT 1"
        ).fetchone()
    if not row:
        raise RuntimeError("No active admin found")
    return int(row[0]), str(row[1]), str(row[2]) if row[2] else None


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
            (
                user_id,
                hashed,
                now.isoformat(),
                (now + timedelta(hours=2)).isoformat(),
                now.isoformat(),
            ),
        )
        con.commit()
    return token, hashed


def delete_temporary_session(hashed: str | None) -> None:
    if not hashed:
        return
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM UserSessions WHERE TokenHash = ?", (hashed,))
        con.commit()


def read_emulator_commands() -> list[str]:
    if not EMULATOR_LOG.exists():
        return []
    commands: list[str] = []
    for line in EMULATOR_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        cmnd = str(entry.get("cmnd") or "")
        if cmnd:
            commands.append(cmnd)
    return commands


def wait_for_command(command: str, seen_count: int, timeout: float = 8.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        commands = read_emulator_commands()
        if len(commands) > seen_count and command in commands[seen_count:]:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Command {command!r} did not reach Tasmota emulator")


def main() -> None:
    user_id, login, password = read_admin_credentials()
    temporary_token_hash: str | None = None
    device_id: int | None = None
    if password:
        _, auth = request("POST", "/auth/login", payload={"login": login, "password": password})
        token = str(auth["token"])
    else:
        token, temporary_token_hash = create_temporary_admin_session(user_id)

    try:
        _, rooms = request("GET", "/rooms", token=token)
        if not rooms:
            _, room = request("POST", "/rooms", token=token, payload={"name": "Tasmota Test Room", "zone": "Tests"})
            room_id = int(room["id"])
        else:
            room_id = int(rooms[0]["id"])

        external_id = f"tasmota-emulator-{int(time.time())}"
        payload = {
            "name": "Tasmota Emulator Test",
            "roomId": room_id,
            "isOn": False,
            "type": "relay",
            "provider": "tasmota",
            "protocol": "http",
            "channel": "wifi",
            "externalId": external_id,
            "manufacturer": "Tasmota",
            "model": "Emulator",
            "connection": {
                "host": "127.0.0.1",
                "port": "8088",
                "path": "/cm",
            },
        }
        _, device = request("POST", "/devices", token=token, payload=payload)
        device_id = int(device["id"])

        before = len(read_emulator_commands())
        request("PUT", f"/devices/{device_id}/toggle", token=token)
        wait_for_command("Power On", before)

        before = len(read_emulator_commands())
        request("PUT", f"/devices/{device_id}/toggle", token=token)
        wait_for_command("Power Off", before)

        _, final_device = request("GET", f"/devices/{device_id}", token=token)
        print(
            json.dumps(
                {
                    "ok": True,
                    "deviceId": device_id,
                    "externalId": external_id,
                    "commands": read_emulator_commands(),
                    "connectionStatus": final_device.get("connectionStatus"),
                    "connectionMessage": final_device.get("connectionMessage"),
                    "isOn": final_device.get("isOn"),
                    "authMode": "login" if password else "temporary_session",
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
