import flet as ft
import requests
from datetime import datetime
from typing import Any

API_BASE = "http://localhost:5000"
DEVICE_TYPES = ["Свет", "Климат", "Камера", "Розетка", "Датчик", "Другое"]


def fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def main(page: ft.Page):
    page.title = "CALHouse / Smart Home"
    page.window_width = 1280
    page.window_height = 860
    page.window_min_width = 1080
    page.window_min_height = 720
    page.padding = 0
    page.spacing = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    state = {
        "tab": 0,
        "dark": False,
    }
    data: dict[str, list[dict[str, Any]]] = {
        "devices": [],
        "rooms": [],
        "scenes": [],
        "rules": [],
        "rule_triggers": [],
        "schedules": [],
        "schedule_runs": [],
        "logs": [],
    }

    content = ft.Container(expand=True, padding=20)

    def palette() -> dict[str, str]:
        if state["dark"]:
            return {
                "bg": "#0b1020",
                "card": "#111827",
                "border": "#1f2a44",
                "text": "#f8fafc",
                "muted": "#94a3b8",
                "field": "#0f172a",
                "nav": "#111827",
                "accent": "#2563eb",
                "danger": "#dc2626",
                "success": "#16a34a",
            }
        return {
            "bg": "#f3f4f6",
            "card": "#ffffff",
            "border": "#e5e7eb",
            "text": "#0f172a",
            "muted": "#64748b",
            "field": "#eef2f7",
            "nav": "#ffffff",
            "accent": "#2563eb",
            "danger": "#dc2626",
            "success": "#16a34a",
        }

    def c(name: str) -> str:
        return palette()[name]

    def T(text: str, **kwargs):
        return ft.Text(text, color=kwargs.pop("color", c("text")), **kwargs)

    def TM(text: str, **kwargs):
        return ft.Text(text, color=kwargs.pop("color", c("muted")), **kwargs)

    def card(*controls: ft.Control, padding: int = 16, expand: bool = False):
        return ft.Container(
            expand=expand,
            padding=padding,
            bgcolor=c("card"),
            border_radius=16,
            border=ft.border.all(1, c("border")),
            content=ft.Column(spacing=10, controls=list(controls)),
        )

    def field(**kwargs):
        return ft.TextField(
            bgcolor=c("field"),
            color=c("text"),
            border_color=c("border"),
            hint_style=ft.TextStyle(color=c("muted")),
            label_style=ft.TextStyle(color=c("muted")),
            **kwargs,
        )

    def dropdown(**kwargs):
        return ft.Dropdown(
            bgcolor=c("field"),
            border_color=c("border"),
            **kwargs,
        )

    def show_message(text: str):
        page.snack_bar = ft.SnackBar(ft.Text(text))
        page.snack_bar.open = True
        page.update()

    def show_dialog(dialog: ft.AlertDialog):
        if dialog not in page.overlay:
            page.overlay.append(dialog)
        page.dialog = dialog
        dialog.open = True
        page.update()

    def close_dialog(dialog: ft.AlertDialog):
        dialog.open = False
        page.update()

    def api_request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 10):
        url = f"{API_BASE}{path}"
        try:
            response = requests.request(method=method.upper(), url=url, json=payload, timeout=timeout)
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {}
                message = error_data.get("message") or error_data.get("error") or f"HTTP {response.status_code}"
                raise RuntimeError(message)
            if not response.text:
                return None
            return response.json()
        except requests.RequestException as ex:
            raise RuntimeError(f"API недоступен: {ex}") from ex

    def load_devices(show_error: bool = False):
        try:
            items = api_request("get", "/api/devices") or []
            data["devices"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def load_rooms(show_error: bool = False):
        try:
            items = api_request("get", "/api/rooms") or []
            data["rooms"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def load_scenes(show_error: bool = False):
        try:
            items = api_request("get", "/api/scenes") or []
            data["scenes"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def load_logs(show_error: bool = False):
        try:
            items = api_request("get", "/api/logs?limit=50") or []
            data["logs"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def load_rules(show_error: bool = False):
        try:
            data["rules"] = api_request("get", "/api/rules") or []
            data["rule_triggers"] = api_request("get", "/api/rules/triggers?limit=30") or []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def load_schedules(show_error: bool = False):
        try:
            data["schedules"] = api_request("get", "/api/schedules") or []
            data["schedule_runs"] = api_request("get", "/api/schedules/runs?limit=30") or []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def refresh_all(show_toast: bool = False):
        load_rooms(show_error=True)
        load_devices(show_error=True)
        load_scenes(show_error=True)
        load_rules(show_error=True)
        load_schedules(show_error=True)
        load_logs(show_error=True)
        if show_toast:
            show_message("Данные обновлены")

    def room_options() -> list[ft.dropdown.Option]:
        return [ft.dropdown.Option(str(room["id"]), room["name"]) for room in data["rooms"]]

    def find_room_name(room_id: int | None) -> str:
        for room in data["rooms"]:
            if room.get("id") == room_id:
                return str(room.get("name", "Комната"))
        return "Комната не указана"

    def stat_card(title: str, value: str, icon: str, tab_index: int | None = None):
        box = ft.Container(
            expand=True,
            padding=16,
            bgcolor=c("card"),
            border_radius=16,
            border=ft.border.all(1, c("border")),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(spacing=6, controls=[TM(title, size=12), T(value, size=24, weight=ft.FontWeight.BOLD)]),
                    ft.Icon(icon, size=30, color=c("accent")),
                ],
            ),
            on_click=(lambda e: switch_tab(tab_index)) if tab_index is not None else None,
        )
        return box

    def switch_tab(index: int):
        state["tab"] = index
        build()

    def confirm_action(title: str, message: str, action):
        dialog_ref = None

        def on_yes(_):
            nonlocal dialog_ref
            if dialog_ref is not None:
                close_dialog(dialog_ref)
            action()

        dialog = ft.AlertDialog(
            modal=True,
            title=T(title, weight=ft.FontWeight.BOLD),
            content=TM(message),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Подтвердить", on_click=on_yes),
            ],
        )
        dialog_ref = dialog
        show_dialog(dialog)

    def open_device_dialog():
        name_tf = field(label="Название", hint_text="Например: Лампа IKEA")
        identifier_tf = field(label="Идентификатор", hint_text="Например: zigbee-lamp-01")
        room_tf = field(label="Комната", hint_text="Например: Спальня")
        provider_dd = dropdown(
            label="Провайдер",
            value="mock",
            options=[ft.dropdown.Option("mock"), ft.dropdown.Option("http"), ft.dropdown.Option("tcp"), ft.dropdown.Option("mqtt")],
        )
        endpoint_tf = field(label="Endpoint/URL", hint_text="Для http: url, для tcp/mqtt: host:port")
        type_dd = dropdown(
            label="Тип устройства",
            value=DEVICE_TYPES[0],
            options=[ft.dropdown.Option(x) for x in DEVICE_TYPES],
        )
        is_on_sw = ft.Switch(label="Включить сразу", value=False)

        def save(_):
            try:
                connection: dict[str, Any] = {}
                endpoint = (endpoint_tf.value or "").strip()
                if provider_dd.value == "http" and endpoint:
                    connection["url"] = endpoint
                elif provider_dd.value in ("tcp", "mqtt") and endpoint:
                    if ":" in endpoint:
                        host, port = endpoint.split(":", 1)
                        connection["host"] = host.strip()
                        connection["port"] = port.strip()
                validate = api_request("post", "/api/devices/validate-connection", {"provider": provider_dd.value, "connection": connection})
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "identifier": (identifier_tf.value or "").strip() or None,
                    "room": (room_tf.value or "").strip(),
                    "isOn": bool(is_on_sw.value),
                    "type": type_dd.value or "Другое",
                    "provider": provider_dd.value or "mock",
                    "connection": connection,
                }
                api_request("post", "/api/devices", payload)
                close_dialog(dialog)
                refresh_all()
                build()
                show_message(f"Устройство добавлено ({'подключено' if validate and validate.get('ok') else 'нет связи'})")
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Добавить устройство", weight=ft.FontWeight.BOLD),
            content=ft.Column(tight=True, spacing=10, controls=[name_tf, identifier_tf, room_tf, provider_dd, endpoint_tf, type_dd, is_on_sw]),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Сохранить", on_click=save),
            ],
        )
        show_dialog(dialog)

    def move_device(device_id: int, room_id_value: str | None):
        if not room_id_value:
            show_message("Выбери комнату")
            return
        try:
            api_request("put", f"/api/devices/{device_id}/room", {"roomId": int(room_id_value)})
            refresh_all()
            build()
            show_message("Привязка устройства обновлена")
        except Exception as ex:
            show_message(str(ex))

    def toggle_device(device_id: int):
        try:
            api_request("put", f"/api/devices/{device_id}/toggle")
            refresh_all()
            build()
        except Exception as ex:
            show_message(str(ex))

    def delete_device(device_id: int, device_name: str):
        def action():
            try:
                api_request("delete", f"/api/devices/{device_id}")
                refresh_all()
                build()
                show_message(f"Устройство удалено: {device_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить устройство", f"Удалить устройство «{device_name}»?", action)

    def open_room_dialog(room: dict[str, Any] | None = None):
        editing = room is not None
        name_tf = field(label="Название комнаты", value=(room or {}).get("name", ""))
        zone_tf = field(label="Зона", value=(room or {}).get("zone", ""), hint_text="Например: Первый этаж")

        def save(_):
            try:
                payload = {"name": (name_tf.value or "").strip(), "zone": (zone_tf.value or "").strip()}
                if editing:
                    api_request("put", f"/api/rooms/{room['id']}", payload)
                    message = "Комната обновлена"
                else:
                    api_request("post", "/api/rooms", payload)
                    message = "Комната создана"
                close_dialog(dialog)
                refresh_all()
                build()
                show_message(message)
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Изменить комнату" if editing else "Создать комнату", weight=ft.FontWeight.BOLD),
            content=ft.Column(tight=True, spacing=10, controls=[name_tf, zone_tf]),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Сохранить", on_click=save),
            ],
        )
        show_dialog(dialog)

    def delete_room(room_id: int, room_name: str):
        def action():
            try:
                api_request("delete", f"/api/rooms/{room_id}")
                refresh_all()
                build()
                show_message(f"Комната удалена: {room_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить комнату", f"Удалить комнату «{room_name}»?", action)

    def open_scene_dialog(scene: dict[str, Any] | None = None):
        editing = scene is not None
        existing_actions = {}
        if scene:
            for action in scene.get("actions", []):
                existing_actions[action.get("deviceId")] = "on" if action.get("targetIsOn") else "off"

        name_tf = field(label="Название сценария", value=(scene or {}).get("name", ""))
        description_tf = field(
            label="Описание",
            multiline=True,
            min_lines=2,
            max_lines=4,
            value=(scene or {}).get("description", ""),
        )

        device_controls: list[tuple[dict[str, Any], ft.Dropdown]] = []
        action_rows: list[ft.Control] = []
        for device in data["devices"]:
            initial = existing_actions.get(device.get("id"), "skip")
            dd = dropdown(
                value=initial,
                width=180,
                options=[
                    ft.dropdown.Option("skip", "Не использовать"),
                    ft.dropdown.Option("on", "Включить"),
                    ft.dropdown.Option("off", "Выключить"),
                ],
            )
            device_controls.append((device, dd))
            action_rows.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                T(str(device.get("name", "Устройство")), weight=ft.FontWeight.BOLD),
                                TM(find_room_name(device.get("roomId")), size=12),
                            ],
                        ),
                        dd,
                    ],
                )
            )

        def save(_):
            actions = []
            order = 1
            for device, dd in device_controls:
                if dd.value == "skip":
                    continue
                actions.append(
                    {
                        "deviceId": int(device.get("id", 0)),
                        "targetIsOn": dd.value == "on",
                        "sortOrder": order,
                    }
                )
                order += 1
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "description": (description_tf.value or "").strip(),
                    "actions": actions,
                }
                if editing:
                    api_request("put", f"/api/scenes/{scene['id']}", payload)
                    message = "Сценарий обновлен"
                else:
                    api_request("post", "/api/scenes", payload)
                    message = "Сценарий создан"
                close_dialog(dialog)
                refresh_all()
                build()
                show_message(message)
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Изменить сценарий" if editing else "Создать сценарий", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=760,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        name_tf,
                        description_tf,
                        T("Действия сценария", weight=ft.FontWeight.BOLD),
                        ft.Container(
                            height=320,
                            content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8, controls=action_rows),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Сохранить", on_click=save),
            ],
        )
        show_dialog(dialog)

    def run_scene(scene_id: int, scene_name: str):
        try:
            api_request("post", f"/api/scenes/{scene_id}/run")
            refresh_all()
            build()
            show_message(f"Сценарий запущен: {scene_name}")
        except Exception as ex:
            show_message(str(ex))

    def delete_scene(scene_id: int, scene_name: str):
        def action():
            try:
                api_request("delete", f"/api/scenes/{scene_id}")
                refresh_all()
                build()
                show_message(f"Сценарий удален: {scene_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить сценарий", f"Удалить сценарий «{scene_name}»?", action)

    def home_view() -> ft.Control:
        recent_logs = data["logs"][:6]
        log_controls = [
            card(
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        T(str(log.get("message", "Событие")), weight=ft.FontWeight.BOLD),
                        TM(fmt_dt(log.get("ts")), size=12),
                    ],
                ),
                TM(f"Источник: {log.get('source', 'api')} · Тип: {log.get('eventType', 'EVENT')}", size=12),
            )
            for log in recent_logs
        ]
        if not log_controls:
            log_controls = [card(TM("История пока пустая"))]

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=18,
            controls=[
                ft.Container(
                    padding=18,
                    border_radius=18,
                    gradient=ft.LinearGradient(colors=["#2563eb", "#9333ea"]),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            T("CALHouse", size=26, weight=ft.FontWeight.BOLD, color="#ffffff"),
                            ft.Text(
                                "Комнаты, привязка устройств и ручные сценарии теперь работают через backend и локальную SQLite БД.",
                                color="#e0e7ff",
                            ),
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.ElevatedButton(
                                        "Открыть комнаты",
                                        icon=ft.Icons.MEETING_ROOM,
                                        on_click=lambda e: switch_tab(2),
                                    ),
                                    ft.OutlinedButton(
                                        "Открыть сценарии",
                                        icon=ft.Icons.AUTO_AWESOME,
                                        on_click=lambda e: switch_tab(3),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                ft.Row(
                    spacing=12,
                    controls=[
                        stat_card("Устройства", str(len(data["devices"])), ft.Icons.DEVICES_OTHER, 1),
                        stat_card("Комнаты", str(len(data["rooms"])), ft.Icons.MEETING_ROOM, 2),
                        stat_card("Сценарии", str(len(data["scenes"])), ft.Icons.AUTO_AWESOME, 3),
                    ],
                ),
                T("Последние события", size=18, weight=ft.FontWeight.BOLD),
                *log_controls,
            ],
        )

    def devices_view() -> ft.Control:
        device_cards = []
        for device in data["devices"]:
            room_dd = dropdown(
                value=str(device.get("roomId")) if device.get("roomId") is not None else None,
                options=room_options(),
                width=220,
            )
            device_cards.append(
                card(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    T(str(device.get("name", "Устройство")), size=18, weight=ft.FontWeight.BOLD),
                                    TM(f"Комната: {device.get('room', 'Комната не указана')}", size=12),
                                    TM(f"Тип: {device.get('type', 'Другое')} · Provider: {device.get('provider', 'mock')}", size=12),
                                    TM(f"ID: {device.get('identifier') or '—'} · Связь: {device.get('connectionStatus', 'unknown')}", size=12),
                                ],
                            ),
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                                border_radius=999,
                                bgcolor="#dcfce7" if device.get("isOn") else "#e2e8f0",
                                content=ft.Text(
                                    "Включено" if device.get("isOn") else "Выключено",
                                    color="#166534" if device.get("isOn") else "#475569",
                                    weight=ft.FontWeight.W_600,
                                ),
                            ),
                        ],
                    ),
                    TM(f"Обновлено: {fmt_dt(device.get('updatedAt'))}"),
                    ft.Row(
                        spacing=10,
                        controls=[
                            ft.ElevatedButton(
                                "Toggle",
                                icon=ft.Icons.POWER_SETTINGS_NEW,
                                on_click=lambda e, device_id=device["id"]: toggle_device(device_id),
                            ),
                            ft.OutlinedButton(
                                "Удалить",
                                icon=ft.Icons.DELETE_OUTLINE,
                                on_click=lambda e, d=device: delete_device(int(d["id"]), str(d.get("name", "Устройство"))),
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=10,
                        controls=[
                            room_dd,
                            ft.OutlinedButton(
                                "Переместить",
                                icon=ft.Icons.SWAP_HORIZ,
                                on_click=lambda e, device_id=device["id"], dd=room_dd: move_device(int(device_id), dd.value),
                            ),
                        ],
                    ),
                )
            )
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Устройства", size=22, weight=ft.FontWeight.BOLD), TM("CRUD устройств и изменение привязки к комнатам")]),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.ElevatedButton("Добавить", icon=ft.Icons.ADD, on_click=lambda e: open_device_dialog()),
                                ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build())),
                            ],
                        ),
                    ],
                ),
                *(device_cards or [card(TM("Устройств пока нет"))]),
            ],
        )

    def rooms_view() -> ft.Control:
        room_cards = []
        devices_by_room: dict[int, list[dict[str, Any]]] = {}
        for device in data["devices"]:
            room_id = device.get("roomId")
            if room_id is None:
                continue
            devices_by_room.setdefault(int(room_id), []).append(device)

        for room in data["rooms"]:
            room_devices = devices_by_room.get(int(room["id"]), [])
            device_lines = room_devices or []
            room_cards.append(
                card(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    T(str(room.get("name", "Комната")), size=18, weight=ft.FontWeight.BOLD),
                                    TM(f"Зона: {room.get('zone', '') or 'Не указана'}", size=12),
                                    TM(f"Устройств: {room.get('deviceCount', 0)}", size=12),
                                ],
                            ),
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, r=room: open_room_dialog(r)),
                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, r=room: delete_room(int(r["id"]), str(r.get("name", "Комната")))),
                                ],
                            ),
                        ],
                    ),
                    T("Устройства в комнате", weight=ft.FontWeight.BOLD),
                    *([
                        ft.Container(
                            padding=10,
                            border_radius=12,
                            bgcolor=c("field"),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            T(str(device.get("name", "Устройство")), weight=ft.FontWeight.BOLD),
                                            TM(f"Тип: {device.get('type', 'Другое')}", size=12),
                                        ],
                                    ),
                                    TM("Вкл" if device.get("isOn") else "Выкл", size=12),
                                ],
                            ),
                        ) for device in device_lines
                    ] if device_lines else [TM("В этой комнате пока нет устройств")]),
                )
            )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Комнаты и зоны", size=22, weight=ft.FontWeight.BOLD), TM("CRUD комнат, зоны и группировка устройств")]),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.ElevatedButton("Создать комнату", icon=ft.Icons.ADD, on_click=lambda e: open_room_dialog()),
                                ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build())),
                            ],
                        ),
                    ],
                ),
                *(room_cards or [card(TM("Комнат пока нет"))]),
            ],
        )

    def scenes_view() -> ft.Control:
        scene_cards = []
        for scene in data["scenes"]:
            action_lines = scene.get("actions", []) or []
            scene_cards.append(
                card(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    T(str(scene.get("name", "Сценарий")), size=18, weight=ft.FontWeight.BOLD),
                                    TM(str(scene.get("description", "")) or "Без описания", size=12),
                                ],
                            ),
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, s=scene: open_scene_dialog(s)),
                                    ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, s=scene: delete_scene(int(s["id"]), str(s.get("name", "Сценарий")))),
                                ],
                            ),
                        ],
                    ),
                    T("Действия", weight=ft.FontWeight.BOLD),
                    *([
                        ft.Container(
                            padding=10,
                            border_radius=12,
                            bgcolor=c("field"),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            T(str(action.get("deviceName", "Устройство")), weight=ft.FontWeight.BOLD),
                                            TM(str(action.get("roomName", "Комната не указана")), size=12),
                                        ],
                                    ),
                                    TM("Включить" if action.get("targetIsOn") else "Выключить", size=12),
                                ],
                            ),
                        ) for action in action_lines
                    ] if action_lines else [TM("В сценарии пока нет действий")]),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=2,
                                controls=[
                                    TM(f"Последний запуск: {fmt_dt(scene.get('lastRunAt'))}", size=12),
                                    TM(f"Статус: {scene.get('lastRunStatus') or 'не запускался'}", size=12),
                                    TM(scene.get("lastRunMessage") or "", size=12),
                                ],
                            ),
                            ft.ElevatedButton(
                                "Запустить",
                                icon=ft.Icons.PLAY_ARROW,
                                on_click=lambda e, s=scene: run_scene(int(s["id"]), str(s.get("name", "Сценарий"))),
                            ),
                        ],
                    ),
                )
            )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Сценарии", size=22, weight=ft.FontWeight.BOLD), TM("Создание, изменение, удаление и ручной запуск сцен")]),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.ElevatedButton("Создать сценарий", icon=ft.Icons.AUTO_AWESOME, on_click=lambda e: open_scene_dialog()),
                                ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build())),
                            ],
                        ),
                    ],
                ),
                *(scene_cards or [card(TM("Сценариев пока нет"))]),
            ],
        )

    def open_rule_dialog():
        name_tf = field(label="Название правила", hint_text="Например: Движение в коридоре")
        source_dd = dropdown(label="Источник события", options=[ft.dropdown.Option(str(d["id"]), f'{d["name"]} (#{d["id"]})') for d in data["devices"]])
        event_tf = field(label="Тип события", value="state")
        op_dd = dropdown(label="Оператор", value="eq", options=[ft.dropdown.Option("eq"), ft.dropdown.Option("neq"), ft.dropdown.Option("gt"), ft.dropdown.Option("gte"), ft.dropdown.Option("lt"), ft.dropdown.Option("lte"), ft.dropdown.Option("contains")])
        value_tf = field(label="Значение для сравнения", hint_text="Например: motion или 27")
        action_dd = dropdown(label="Действие", value="scene", options=[ft.dropdown.Option("scene"), ft.dropdown.Option("device")])
        scene_dd = dropdown(label="Сценарий", options=[ft.dropdown.Option(str(s["id"]), s["name"]) for s in data["scenes"]])
        target_device_dd = dropdown(label="Устройство", options=[ft.dropdown.Option(str(d["id"]), d["name"]) for d in data["devices"]])
        target_state_sw = ft.Switch(label="Целевое состояние ON", value=True)

        def save(_):
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "isEnabled": True,
                    "sourceDeviceId": int(source_dd.value),
                    "eventType": (event_tf.value or "state").strip(),
                    "operator": op_dd.value or "eq",
                    "compareValue": (value_tf.value or "").strip(),
                    "actionType": action_dd.value or "scene",
                    "actionSceneId": int(scene_dd.value) if (action_dd.value == "scene" and scene_dd.value) else None,
                    "actionDeviceId": int(target_device_dd.value) if (action_dd.value == "device" and target_device_dd.value) else None,
                    "actionTargetIsOn": bool(target_state_sw.value) if action_dd.value == "device" else None,
                }
                api_request("post", "/api/rules", payload)
                close_dialog(dialog)
                refresh_all()
                build()
                show_message("Правило создано")
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Создать правило", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=760, content=ft.Column(tight=True, spacing=10, controls=[name_tf, source_dd, event_tf, op_dd, value_tf, action_dd, scene_dd, target_device_dd, target_state_sw])),
            actions=[ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)), ft.ElevatedButton("Сохранить", on_click=save)],
        )
        show_dialog(dialog)

    def rules_view() -> ft.Control:
        def send_event(device_id: int):
            event_tf = field(label="Тип события", value="state")
            value_tf = field(label="Значение", value="motion")

            def run_event(_):
                try:
                    api_request("post", "/api/rules/process-event", {"deviceId": device_id, "eventType": event_tf.value, "value": value_tf.value})
                    close_dialog(dialog)
                    refresh_all()
                    build()
                    show_message("Событие обработано")
                except Exception as ex:
                    show_message(str(ex))

            dialog = ft.AlertDialog(
                modal=True,
                title=T("Тест события датчика", weight=ft.FontWeight.BOLD),
                content=ft.Column(tight=True, spacing=10, controls=[event_tf, value_tf]),
                actions=[ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)), ft.ElevatedButton("Отправить", on_click=run_event)],
            )
            show_dialog(dialog)

        cards = []
        for rule in data["rules"]:
            cards.append(card(
                T(str(rule.get("name", "Правило")), size=18, weight=ft.FontWeight.BOLD),
                TM(f"Если {rule.get('eventType')} {rule.get('operator')} {rule.get('compareValue')} (device #{rule.get('sourceDeviceId')})"),
                TM(f"Действие: {rule.get('actionType')} · срабатываний: {rule.get('triggerCount', 0)}"),
                ft.Row(spacing=8, controls=[
                    ft.OutlinedButton("Тест события", on_click=lambda e, d=rule.get("sourceDeviceId"): send_event(int(d))),
                    ft.OutlinedButton("Удалить", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e, rid=rule.get("id"): (api_request("delete", f"/api/rules/{int(rid)}"), refresh_all(), build())),
                ])
            ))
        trigger_cards = [card(T(str(t.get("ruleName", "Триггер")), weight=ft.FontWeight.BOLD), TM(f"{fmt_dt(t.get('triggeredAt'))} · {t.get('message')}")) for t in data["rule_triggers"][:10]]
        return ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Column(spacing=4, controls=[T("Автоматизация по событиям", size=22, weight=ft.FontWeight.BOLD), TM("Правила вида if-event-then-action")]),
                ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать правило", icon=ft.Icons.ADD, on_click=lambda e: open_rule_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()))]),
            ]),
            *(cards or [card(TM("Правил пока нет"))]),
            T("Последние срабатывания", size=18, weight=ft.FontWeight.BOLD),
            *(trigger_cards or [card(TM("Срабатываний пока нет"))]),
        ])

    def open_schedule_dialog():
        name_tf = field(label="Название расписания", hint_text="Например: Утренний запуск")
        days_tf = field(label="Дни недели", value="1,2,3,4,5,6,7", hint_text="1=Пн ... 7=Вс")
        time_tf = field(label="Время HH:mm", value="08:00")
        action_dd = dropdown(label="Действие", value="scene", options=[ft.dropdown.Option("scene"), ft.dropdown.Option("device")])
        scene_dd = dropdown(label="Сценарий", options=[ft.dropdown.Option(str(s["id"]), s["name"]) for s in data["scenes"]])
        device_dd = dropdown(label="Устройство", options=[ft.dropdown.Option(str(d["id"]), d["name"]) for d in data["devices"]])
        target_sw = ft.Switch(label="Целевое состояние ON", value=True)

        def save(_):
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "isEnabled": True,
                    "daysOfWeek": (days_tf.value or "").strip(),
                    "timeOfDay": (time_tf.value or "").strip(),
                    "actionType": action_dd.value or "scene",
                    "actionSceneId": int(scene_dd.value) if action_dd.value == "scene" and scene_dd.value else None,
                    "actionDeviceId": int(device_dd.value) if action_dd.value == "device" and device_dd.value else None,
                    "actionTargetIsOn": bool(target_sw.value) if action_dd.value == "device" else None,
                }
                api_request("post", "/api/schedules", payload)
                close_dialog(dialog)
                refresh_all()
                build()
                show_message("Расписание создано")
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Создать расписание", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=760, content=ft.Column(tight=True, spacing=10, controls=[name_tf, days_tf, time_tf, action_dd, scene_dd, device_dd, target_sw])),
            actions=[ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)), ft.ElevatedButton("Сохранить", on_click=save)],
        )
        show_dialog(dialog)

    def schedules_view() -> ft.Control:
        cards = []
        for schedule in data["schedules"]:
            cards.append(card(
                T(str(schedule.get("name", "Расписание")), size=18, weight=ft.FontWeight.BOLD),
                TM(f"Дни: {schedule.get('daysOfWeek')} · Время: {schedule.get('timeOfDay')}"),
                TM(f"Действие: {schedule.get('actionType')} · Последний запуск: {fmt_dt(schedule.get('lastRunAt'))}"),
                ft.Row(spacing=8, controls=[
                    ft.OutlinedButton("Удалить", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e, sid=schedule.get("id"): (api_request("delete", f"/api/schedules/{int(sid)}"), refresh_all(), build())),
                ])
            ))
        run_cards = [card(T(str(r.get("scheduleName", "Запуск")), weight=ft.FontWeight.BOLD), TM(f"{fmt_dt(r.get('startedAt'))} · {r.get('message')}")) for r in data["schedule_runs"][:10]]
        return ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Column(spacing=4, controls=[T("Расписание", size=22, weight=ft.FontWeight.BOLD), TM("Запуск действий по времени и дням недели")]),
                ft.Row(spacing=10, controls=[
                    ft.ElevatedButton("Создать расписание", icon=ft.Icons.SCHEDULE, on_click=lambda e: open_schedule_dialog()),
                    ft.OutlinedButton("Запустить планировщик", on_click=lambda e: (api_request("post", "/api/schedules/run-due", {}), refresh_all(True), build())),
                ]),
            ]),
            *(cards or [card(TM("Расписаний пока нет"))]),
            T("История запусков", size=18, weight=ft.FontWeight.BOLD),
            *(run_cards or [card(TM("История запусков пока пустая"))]),
        ])

    def history_view() -> ft.Control:
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("История и логирование", size=22, weight=ft.FontWeight.BOLD), TM("Логи backend и результаты выполнения сцен")]),
                        ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build())),
                    ],
                ),
                *([
                    card(
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                T(str(log.get("message", "Событие")), weight=ft.FontWeight.BOLD),
                                TM(fmt_dt(log.get("ts")), size=12),
                            ],
                        ),
                        TM(f"Тип: {log.get('eventType', 'EVENT')} · Источник: {log.get('source', 'api')}", size=12),
                        TM(f"severity={log.get('severity', 'info')} · deviceId={log.get('deviceId')} · sceneId={log.get('sceneId')}", size=12),
                    ) for log in data["logs"]
                ] or [card(TM("Логи пока пустые"))]),
            ],
        )

    def settings_view() -> ft.Control:
        dark_sw = ft.Switch(label="Темная тема", value=state["dark"])

        def save_settings(_):
            state["dark"] = bool(dark_sw.value)
            page.theme_mode = ft.ThemeMode.DARK if state["dark"] else ft.ThemeMode.LIGHT
            build()
            show_message("Настройки обновлены")

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                T("Настройки", size=22, weight=ft.FontWeight.BOLD),
                card(
                    T("Интерфейс", weight=ft.FontWeight.BOLD),
                    dark_sw,
                    ft.ElevatedButton("Сохранить", on_click=save_settings),
                ),
                card(
                    T("Подключение к API", weight=ft.FontWeight.BOLD),
                    TM(f"Base URL: {API_BASE}"),
                    TM("Backend должен быть запущен на ASP.NET Core приложении из backend/CalHouse.Api"),
                ),
            ],
        )

    nav = ft.NavigationBar(
        selected_index=0,
        bgcolor=c("nav"),
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Главная"),
            ft.NavigationBarDestination(icon=ft.Icons.FLASH_ON_OUTLINED, selected_icon=ft.Icons.FLASH_ON, label="Устройства"),
            ft.NavigationBarDestination(icon=ft.Icons.MEETING_ROOM, selected_icon=ft.Icons.MEETING_ROOM, label="Комнаты"),
            ft.NavigationBarDestination(icon=ft.Icons.AUTO_AWESOME, selected_icon=ft.Icons.AUTO_AWESOME, label="Сценарии"),
            ft.NavigationBarDestination(icon=ft.Icons.SENSORS, selected_icon=ft.Icons.SENSORS, label="Правила"),
            ft.NavigationBarDestination(icon=ft.Icons.SCHEDULE, selected_icon=ft.Icons.SCHEDULE, label="Расписание"),
            ft.NavigationBarDestination(icon=ft.Icons.HISTORY_OUTLINED, selected_icon=ft.Icons.HISTORY, label="История"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Настройки"),
        ],
    )

    def on_nav_change(e: ft.ControlEvent):
        state["tab"] = int(e.control.selected_index)
        build()

    nav.on_change = on_nav_change

    def build():
        page.bgcolor = c("bg")
        page.navigation_bar = nav
        nav.selected_index = state["tab"]
        page.appbar = ft.AppBar(
            bgcolor=c("nav"),
            title=ft.Text("CALHouse", color=c("text"), weight=ft.FontWeight.BOLD),
            actions=[ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()), icon_color=c("text"))],
        )

        views = {
            0: home_view,
            1: devices_view,
            2: rooms_view,
            3: scenes_view,
            4: rules_view,
            5: schedules_view,
            6: history_view,
            7: settings_view,
        }
        content.content = views.get(state["tab"], home_view)()
        page.controls.clear()
        page.add(content)
        page.update()

    refresh_all()
    build()


ft.run(main)
