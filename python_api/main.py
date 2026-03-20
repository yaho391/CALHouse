from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "calhouse.db"

app = FastAPI(title="CALHouse Python API", version="1.0.0")


class RoomCreate(BaseModel):
    name: str = Field(min_length=1)


class RoomUpdate(BaseModel):
    name: str = Field(min_length=1)


class SceneActionIn(BaseModel):
    device_id: int
    is_on: bool


class SceneWrite(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    actions: list[SceneActionIn] = Field(min_length=1)


class DeviceRoomUpdate(BaseModel):
    room_id: int


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.on_event("startup")
def startup() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            room_id INTEGER NOT NULL,
            is_on INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(room_id) REFERENCES rooms(id)
        );

        CREATE TABLE IF NOT EXISTS scenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS scene_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            is_on INTEGER NOT NULL,
            FOREIGN KEY(scene_id) REFERENCES scenes(id) ON DELETE CASCADE,
            FOREIGN KEY(device_id) REFERENCES devices(id)
        );

        CREATE TABLE IF NOT EXISTS scene_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at_utc TEXT NOT NULL,
            finished_at_utc TEXT NOT NULL,
            details_json TEXT NOT NULL,
            FOREIGN KEY(scene_id) REFERENCES scenes(id)
        );
        """
    )

    room_count = conn.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    if room_count == 0:
        conn.executemany("INSERT INTO rooms(name) VALUES(?)", [("Гостиная",), ("Кухня",), ("Спальня",)])
        conn.executemany(
            "INSERT INTO devices(name, room_id, is_on) VALUES(?, ?, ?)",
            [("Термостат", 1, 0), ("Освещение", 2, 1), ("Камера", 1, 1)],
        )

    conn.commit()
    conn.close()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "CALHouse Python API is running"}


@app.get("/api/rooms")
def get_rooms() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id, name FROM rooms ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/rooms", status_code=201)
def create_room(payload: RoomCreate) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute("INSERT INTO rooms(name) VALUES(?)", (payload.name.strip(),))
        conn.commit()
        room_id = cur.lastrowid
        room = conn.execute("SELECT id, name FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return dict(room)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail={"error": "Room name already exists", "code": "ROOM_ALREADY_EXISTS"})
    finally:
        conn.close()


@app.put("/api/rooms/{room_id}")
def rename_room(room_id: int, payload: RoomUpdate) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute("UPDATE rooms SET name = ? WHERE id = ?", (payload.name.strip(), room_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail={"error": "Room not found", "code": "ROOM_NOT_FOUND"})
        conn.commit()
        row = conn.execute("SELECT id, name FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail={"error": "Room name already exists", "code": "ROOM_ALREADY_EXISTS"})
    finally:
        conn.close()


@app.delete("/api/rooms/{room_id}", status_code=204)
def delete_room(room_id: int) -> None:
    conn = get_conn()
    room = conn.execute("SELECT id FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": "Room not found", "code": "ROOM_NOT_FOUND"})

    count = conn.execute("SELECT COUNT(*) FROM devices WHERE room_id = ?", (room_id,)).fetchone()[0]
    if count > 0:
        conn.close()
        raise HTTPException(status_code=409, detail={"error": "Room has devices", "code": "ROOM_NOT_EMPTY"})

    conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
    conn.commit()
    conn.close()


@app.get("/api/rooms/{room_id}/devices")
def get_room_devices(room_id: int) -> list[dict]:
    conn = get_conn()
    room = conn.execute("SELECT id FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": "Room not found", "code": "ROOM_NOT_FOUND"})

    rows = conn.execute(
        "SELECT d.id, d.name, d.room_id, r.name AS room_name, d.is_on FROM devices d JOIN rooms r ON r.id = d.room_id WHERE room_id = ? ORDER BY d.id",
        (room_id,),
    ).fetchall()
    conn.close()
    return [
        {"id": row["id"], "name": row["name"], "roomId": row["room_id"], "room": row["room_name"], "isOn": bool(row["is_on"])}
        for row in rows
    ]


@app.get("/api/devices")
def get_devices(room_id: int | None = Query(default=None)) -> list[dict]:
    conn = get_conn()
    query = "SELECT d.id, d.name, d.room_id, r.name AS room_name, d.is_on FROM devices d JOIN rooms r ON r.id = d.room_id"
    params: tuple = ()
    if room_id is not None:
        query += " WHERE d.room_id = ?"
        params = (room_id,)
    query += " ORDER BY d.id"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [
        {"id": row["id"], "name": row["name"], "roomId": row["room_id"], "room": row["room_name"], "isOn": bool(row["is_on"])}
        for row in rows
    ]


@app.put("/api/devices/{device_id}/room")
def reassign_device_room(device_id: int, payload: DeviceRoomUpdate) -> dict:
    conn = get_conn()
    room = conn.execute("SELECT id FROM rooms WHERE id = ?", (payload.room_id,)).fetchone()
    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": "Room not found", "code": "ROOM_NOT_FOUND"})

    cur = conn.execute("UPDATE devices SET room_id = ? WHERE id = ?", (payload.room_id, device_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": "Device not found", "code": "DEVICE_NOT_FOUND"})

    conn.commit()
    row = conn.execute(
        "SELECT d.id, d.name, d.room_id, r.name AS room_name, d.is_on FROM devices d JOIN rooms r ON r.id = d.room_id WHERE d.id = ?",
        (device_id,),
    ).fetchone()
    conn.close()
    return {"id": row["id"], "name": row["name"], "roomId": row["room_id"], "room": row["room_name"], "isOn": bool(row["is_on"])}


@app.get("/api/scenes")
def get_scenes() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT id, name, description FROM scenes ORDER BY id").fetchall()
    scenes = []
    for row in rows:
        actions = conn.execute("SELECT device_id, is_on FROM scene_actions WHERE scene_id = ? ORDER BY id", (row["id"],)).fetchall()
        scenes.append(
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "actions": [{"deviceId": a["device_id"], "isOn": bool(a["is_on"])} for a in actions],
            }
        )
    conn.close()
    return scenes


@app.post("/api/scenes", status_code=201)
def create_scene(payload: SceneWrite) -> dict:
    return _save_scene(None, payload)


@app.put("/api/scenes/{scene_id}")
def update_scene(scene_id: int, payload: SceneWrite) -> dict:
    return _save_scene(scene_id, payload)


def _save_scene(scene_id: int | None, payload: SceneWrite) -> dict:
    conn = get_conn()
    missing = [a.device_id for a in payload.actions if conn.execute("SELECT 1 FROM devices WHERE id = ?", (a.device_id,)).fetchone() is None]
    if missing:
        conn.close()
        raise HTTPException(status_code=400, detail={"error": f"Device not found: {missing[0]}", "code": "DEVICE_NOT_FOUND"})

    if scene_id is None:
        cur = conn.execute("INSERT INTO scenes(name, description) VALUES(?, ?)", (payload.name.strip(), payload.description))
        scene_id = cur.lastrowid
    else:
        cur = conn.execute("UPDATE scenes SET name = ?, description = ? WHERE id = ?", (payload.name.strip(), payload.description, scene_id))
        if cur.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail={"error": "Scene not found", "code": "SCENE_NOT_FOUND"})
        conn.execute("DELETE FROM scene_actions WHERE scene_id = ?", (scene_id,))

    conn.executemany(
        "INSERT INTO scene_actions(scene_id, device_id, is_on) VALUES(?, ?, ?)",
        [(scene_id, a.device_id, int(a.is_on)) for a in payload.actions],
    )
    conn.commit()
    scene = conn.execute("SELECT id, name, description FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    conn.close()
    return {
        "id": scene["id"],
        "name": scene["name"],
        "description": scene["description"],
        "actions": [{"deviceId": a.device_id, "isOn": a.is_on} for a in payload.actions],
    }


@app.delete("/api/scenes/{scene_id}", status_code=204)
def delete_scene(scene_id: int) -> None:
    conn = get_conn()
    cur = conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": "Scene not found", "code": "SCENE_NOT_FOUND"})
    conn.commit()
    conn.close()


@app.post("/api/scenes/{scene_id}/run")
def run_scene(scene_id: int) -> dict:
    conn = get_conn()
    scene = conn.execute("SELECT id, name FROM scenes WHERE id = ?", (scene_id,)).fetchone()
    if not scene:
        conn.close()
        raise HTTPException(status_code=404, detail={"error": "Scene not found", "code": "SCENE_NOT_FOUND"})

    actions = conn.execute("SELECT device_id, is_on FROM scene_actions WHERE scene_id = ? ORDER BY id", (scene_id,)).fetchall()
    started = now_iso()
    items = []
    for action in actions:
        cur = conn.execute("UPDATE devices SET is_on = ? WHERE id = ?", (action["is_on"], action["device_id"]))
        status: Literal["applied", "device_not_found"] = "applied" if cur.rowcount else "device_not_found"
        items.append({"deviceId": action["device_id"], "requestedState": bool(action["is_on"]), "status": status})

    status = "completed" if all(i["status"] == "applied" for i in items) else "completed_with_warnings"
    finished = now_iso()

    import json

    cur = conn.execute(
        "INSERT INTO scene_executions(scene_id, status, started_at_utc, finished_at_utc, details_json) VALUES(?, ?, ?, ?, ?)",
        (scene_id, status, started, finished, json.dumps(items, ensure_ascii=False)),
    )
    conn.commit()
    execution_id = cur.lastrowid
    conn.close()

    return {
        "id": execution_id,
        "sceneId": scene_id,
        "sceneName": scene["name"],
        "status": status,
        "startedAtUtc": started,
        "finishedAtUtc": finished,
        "results": items,
    }


@app.get("/api/scenes/executions")
def scene_executions(scene_id: int | None = Query(default=None)) -> list[dict]:
    import json

    conn = get_conn()
    query = "SELECT e.id, e.scene_id, s.name AS scene_name, e.status, e.started_at_utc, e.finished_at_utc, e.details_json FROM scene_executions e JOIN scenes s ON s.id = e.scene_id"
    params: tuple = ()
    if scene_id is not None:
        query += " WHERE e.scene_id = ?"
        params = (scene_id,)
    query += " ORDER BY e.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "sceneId": row["scene_id"],
            "sceneName": row["scene_name"],
            "status": row["status"],
            "startedAtUtc": row["started_at_utc"],
            "finishedAtUtc": row["finished_at_utc"],
            "results": json.loads(row["details_json"]),
        }
        for row in rows
    ]
