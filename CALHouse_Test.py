import flet as ft
import requests
from datetime import datetime
from typing import Any

API_BASE = "http://localhost:5000"
DEFAULT_DEVICE_TYPES = ["Свет", "Климат", "Камера", "Розетка", "Датчик", "Замок", "Штора", "Другое"]
DEFAULT_RULE_OPERATORS = ["=", "!=", ">", ">=", "<", "<=", "contains"]
DEFAULT_ACTION_KINDS = ["device_state", "scene_run"]
DEFAULT_SCHEDULE_DAYS = [
    {"value": 1, "title": "Пн"},
    {"value": 2, "title": "Вт"},
    {"value": 3, "title": "Ср"},
    {"value": 4, "title": "Чт"},
    {"value": 5, "title": "Пт"},
    {"value": 6, "title": "Сб"},
    {"value": 7, "title": "Вс"},
]


def fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def main(page: ft.Page):
    page.title = "CALHouse / Smart Home"
    page.window_width = 1400
    page.window_height = 900
    page.window_min_width = 1180
    page.window_min_height = 760
    page.padding = 0
    page.spacing = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    state = {"tab": 0, "dark": False}
    data: dict[str, Any] = {
        "catalog": {},
        "devices": [],
        "rooms": [],
        "scenes": [],
        "rules": [],
        "schedules": [],
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
        return ft.Dropdown(bgcolor=c("field"), border_color=c("border"), **kwargs)

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

    def load_catalog(show_error: bool = False):
        try:
            data["catalog"] = api_request("get", "/api/device-catalog") or {}
        except Exception as ex:
            data["catalog"] = {}
            if show_error:
                show_message(str(ex))

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

    def load_rules(show_error: bool = False):
        try:
            items = api_request("get", "/api/rules") or []
            data["rules"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def load_schedules(show_error: bool = False):
        try:
            items = api_request("get", "/api/schedules") or []
            data["schedules"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def load_logs(show_error: bool = False):
        try:
            items = api_request("get", "/api/logs?limit=80") or []
            data["logs"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    def refresh_all(show_toast: bool = False):
        load_catalog(show_error=True)
        load_rooms(show_error=True)
        load_devices(show_error=True)
        load_scenes(show_error=True)
        load_rules(show_error=True)
        load_schedules(show_error=True)
        load_logs(show_error=True)
        if show_toast:
            show_message("Данные обновлены")

    def device_types() -> list[str]:
        return data["catalog"].get("deviceTypes") or DEFAULT_DEVICE_TYPES

    def providers() -> list[dict[str, Any]]:
        items = data["catalog"].get("providers") or []
        return items if isinstance(items, list) else []

    def provider_map() -> dict[str, dict[str, Any]]:
        return {str(item.get("key", "")): item for item in providers()}

    def rule_operators() -> list[str]:
        return data["catalog"].get("ruleOperators") or DEFAULT_RULE_OPERATORS

    def action_kinds() -> list[str]:
        return data["catalog"].get("actionKinds") or DEFAULT_ACTION_KINDS

    def schedule_days() -> list[dict[str, Any]]:
        return data["catalog"].get("scheduleDays") or DEFAULT_SCHEDULE_DAYS

    def room_options() -> list[ft.dropdown.Option]:
        return [ft.dropdown.Option(str(room["id"]), room["name"]) for room in data["rooms"]]

    def device_options(sensor_first: bool = False) -> list[ft.dropdown.Option]:
        items = data["devices"]
        if sensor_first:
            items = sorted(items, key=lambda item: (0 if item.get("type") == "Датчик" else 1, str(item.get("name", ""))))
        return [ft.dropdown.Option(str(device["id"]), device["name"]) for device in items]

    def scene_options() -> list[ft.dropdown.Option]:
        return [ft.dropdown.Option(str(scene["id"]), scene["name"]) for scene in data["scenes"]]

    def find_room_name(room_id: int | None) -> str:
        for room in data["rooms"]:
            if room.get("id") == room_id:
                return str(room.get("name", "Комната"))
        return "Комната не указана"

    def provider_title(key: str | None) -> str:
        if not key:
            return "—"
        item = provider_map().get(key)
        return str(item.get("title", key)) if item else str(key)

    def action_kind_title(kind: str | None) -> str:
        if kind == "device_state":
            return "Изменить устройство"
        if kind == "scene_run":
            return "Запустить сценарий"
        return str(kind or "—")

    def schedule_days_title(days: list[int] | None) -> str:
        days = days or []
        lookup = {int(item["value"]): str(item["title"]) for item in schedule_days()}
        return ", ".join(lookup.get(day, str(day)) for day in days) or "—"

    def stat_card(title: str, value: str, icon: str, tab_index: int | None = None):
        return ft.Container(
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

    def status_chip(text: str, status: str | None):
        mapping = {
            "connected": ("#dcfce7", "#166534"),
            "completed": ("#dcfce7", "#166534"),
            "enabled": ("#dbeafe", "#1d4ed8"),
            "no_connection": ("#fee2e2", "#991b1b"),
            "warning": ("#fef3c7", "#92400e"),
            "disabled": ("#e2e8f0", "#475569"),
            "unknown": ("#e2e8f0", "#475569"),
        }
        bg, fg = mapping.get(str(status or "unknown"), ("#e2e8f0", "#475569"))
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            border_radius=999,
            bgcolor=bg,
            content=ft.Text(text, color=fg, weight=ft.FontWeight.W_600, size=12),
        )

    def bool_chip(value: bool):
        return status_chip("Включено" if value else "Выключено", "connected" if value else "disabled")

    def open_device_dialog(device: dict[str, Any] | None = None):
        editing = device is not None
        providers_dict = provider_map()
        provider_key = str((device or {}).get("provider", "mock") or "mock")
        provider_info = providers_dict.get(provider_key, {"protocol": "manual", "channel": "local", "note": ""})

        name_tf = field(label="Название", value=(device or {}).get("name", ""), hint_text="Например: Лампа IKEA")
        external_id_tf = field(label="Идентификатор", value=(device or {}).get("externalId", ""), hint_text="Например: kitchen-light-01")
        manufacturer_tf = field(label="Производитель", value=(device or {}).get("manufacturer", ""))
        model_tf = field(label="Модель", value=(device or {}).get("model", ""))
        type_dd = dropdown(label="Тип устройства", value=(device or {}).get("type", device_types()[0]), options=[ft.dropdown.Option(x) for x in device_types()])
        provider_dd = dropdown(label="Провайдер", value=provider_key, options=[ft.dropdown.Option(item.get("key"), item.get("title")) for item in providers()])
        protocol_tf = field(label="Протокол", value=str((device or {}).get("protocol", provider_info.get("protocol", "manual"))))
        channel_tf = field(label="Канал", value=str((device or {}).get("channel", provider_info.get("channel", "local"))))
        room_dd = dropdown(label="Комната из списка", value=str(device.get("roomId")) if editing and device.get("roomId") is not None else None, options=room_options())
        new_room_tf = field(label="Или новая комната", value="" if editing else (device or {}).get("room", ""), hint_text="Оставь пустым, если выбрал комнату выше")
        is_on_sw = ft.Switch(label="Включить сразу", value=bool((device or {}).get("isOn", False)))

        existing_conn = (device or {}).get("connection", {}) or {}
        host_tf = field(label="Host / IP", value=existing_conn.get("host", ""))
        port_tf = field(label="Port", value=str(existing_conn.get("port", "")))
        url_tf = field(label="URL", value=existing_conn.get("url", ""))
        path_tf = field(label="Path", value=existing_conn.get("path", ""))
        topic_tf = field(label="Topic / Entity ID", value=existing_conn.get("topic", existing_conn.get("entity_id", "")))
        username_tf = field(label="Username", value=existing_conn.get("username", ""))
        password_tf = field(label="Password / Device key", value=existing_conn.get("password", existing_conn.get("device_key", "")), password=True, can_reveal_password=True)
        token_tf = field(label="Token", value=existing_conn.get("token", ""), password=True, can_reveal_password=True)
        note_text = TM(str(provider_info.get("note", "")), size=12)
        test_result = TM("", size=12)

        def collect_connection() -> dict[str, str]:
            connection = {}
            pairs = {
                "host": host_tf.value,
                "port": port_tf.value,
                "url": url_tf.value,
                "path": path_tf.value,
                "topic": topic_tf.value,
                "entity_id": topic_tf.value if provider_dd.value == "homeassistant" else "",
                "username": username_tf.value,
                "password": password_tf.value,
                "device_key": password_tf.value,
                "token": token_tf.value,
            }
            for key, value in pairs.items():
                clean = (value or "").strip()
                if clean:
                    connection[key] = clean
            return connection

        def on_provider_change(_):
            info = providers_dict.get(str(provider_dd.value), {})
            if not protocol_tf.value:
                protocol_tf.value = str(info.get("protocol", "manual"))
            if not channel_tf.value:
                channel_tf.value = str(info.get("channel", "local"))
            note_text.value = str(info.get("note", ""))
            page.update()

        provider_dd.on_change = on_provider_change

        def test_connection(_):
            try:
                result = api_request(
                    "post",
                    "/api/devices/validate-connection",
                    {
                        "provider": provider_dd.value or "mock",
                        "protocol": (protocol_tf.value or "manual").strip(),
                        "connection": collect_connection(),
                    },
                ) or {}
                status = str(result.get("status", "unknown"))
                test_result.value = f"Проверка: {result.get('message', 'готово')}"
                if status == "connected":
                    show_message("Связь проверена: подключено")
                elif status == "no_connection":
                    show_message("Связь проверена: нет связи")
                else:
                    show_message(str(result.get("message", "Проверка завершена")))
                page.update()
            except Exception as ex:
                show_message(str(ex))

        def save(_):
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "roomId": int(room_dd.value) if room_dd.value else None,
                    "room": (new_room_tf.value or "").strip() or None,
                    "isOn": bool(is_on_sw.value),
                    "type": type_dd.value or "Другое",
                    "provider": provider_dd.value or "mock",
                    "protocol": (protocol_tf.value or "manual").strip(),
                    "channel": (channel_tf.value or "local").strip(),
                    "externalId": (external_id_tf.value or "").strip(),
                    "manufacturer": (manufacturer_tf.value or "").strip(),
                    "model": (model_tf.value or "").strip(),
                    "connection": collect_connection(),
                }
                if editing:
                    created = api_request("put", f"/api/devices/{device['id']}", payload)
                    message = "Устройство обновлено"
                else:
                    created = api_request("post", "/api/devices", payload)
                    message = "Устройство добавлено"
                close_dialog(dialog)
                refresh_all()
                build()
                status = created.get("connectionStatus") if isinstance(created, dict) else None
                status_message = created.get("connectionMessage") if isinstance(created, dict) else ""
                show_message(f"{message}. Статус: {status or 'unknown'} {status_message or ''}".strip())
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Изменить устройство" if editing else "Добавить устройство", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=860,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Row(spacing=10, controls=[name_tf, external_id_tf]),
                        ft.Row(spacing=10, controls=[manufacturer_tf, model_tf]),
                        ft.Row(spacing=10, controls=[type_dd, provider_dd]),
                        ft.Row(spacing=10, controls=[protocol_tf, channel_tf]),
                        ft.Row(spacing=10, controls=[room_dd, new_room_tf]),
                        is_on_sw,
                        T("Параметры подключения", weight=ft.FontWeight.BOLD),
                        note_text,
                        ft.Row(spacing=10, controls=[host_tf, port_tf]),
                        ft.Row(spacing=10, controls=[url_tf, path_tf]),
                        ft.Row(spacing=10, controls=[topic_tf, username_tf]),
                        ft.Row(spacing=10, controls=[password_tf, token_tf]),
                        test_result,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Тест связи", on_click=test_connection),
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
        description_tf = field(label="Описание", multiline=True, min_lines=2, max_lines=4, value=(scene or {}).get("description", ""))

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
            for item_device, dd in device_controls:
                if dd.value == "skip":
                    continue
                actions.append({"deviceId": int(item_device.get("id", 0)), "targetIsOn": dd.value == "on", "sortOrder": order})
                order += 1
            try:
                payload = {"name": (name_tf.value or "").strip(), "description": (description_tf.value or "").strip(), "actions": actions}
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
                        ft.Container(height=320, content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8, controls=action_rows)),
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

    def open_rule_dialog(rule: dict[str, Any] | None = None):
        editing = rule is not None
        name_tf = field(label="Название правила", value=(rule or {}).get("name", ""))
        description_tf = field(label="Описание", value=(rule or {}).get("description", ""), multiline=True, min_lines=2, max_lines=3)
        enabled_sw = ft.Switch(label="Правило активно", value=bool((rule or {}).get("isEnabled", True)))
        trigger_device_dd = dropdown(label="Датчик / источник", value=str(rule.get("triggerDeviceId")) if editing and rule.get("triggerDeviceId") is not None else None, options=device_options(sensor_first=True))
        event_type_tf = field(label="Тип события", value=(rule or {}).get("triggerEventType", "motion"), hint_text="Например: motion, temperature, state")
        operator_dd = dropdown(label="Оператор", value=(rule or {}).get("comparisonOperator", "="), options=[ft.dropdown.Option(x) for x in rule_operators()])
        compare_tf = field(label="Сравнить с", value=(rule or {}).get("compareValue", "true"), hint_text="Например: true, 25, open")
        action_kind_dd = dropdown(label="Тип действия", value=(rule or {}).get("actionKind", "device_state"), options=[ft.dropdown.Option(x, action_kind_title(x)) for x in action_kinds()])
        action_device_dd = dropdown(label="Целевое устройство", value=str(rule.get("actionDeviceId")) if editing and rule.get("actionDeviceId") is not None else None, options=device_options())
        action_state_dd = dropdown(
            label="Целевое состояние",
            value="on" if (rule or {}).get("actionTargetIsOn", True) else "off",
            options=[ft.dropdown.Option("on", "Включить"), ft.dropdown.Option("off", "Выключить")],
        )
        action_scene_dd = dropdown(label="Или сценарий", value=str(rule.get("actionSceneId")) if editing and rule.get("actionSceneId") is not None else None, options=scene_options())

        def save(_):
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "description": (description_tf.value or "").strip(),
                    "isEnabled": bool(enabled_sw.value),
                    "triggerDeviceId": int(trigger_device_dd.value or 0),
                    "eventType": (event_type_tf.value or "").strip(),
                    "comparisonOperator": operator_dd.value or "=",
                    "compareValue": (compare_tf.value or "").strip(),
                    "actionKind": action_kind_dd.value or "device_state",
                    "actionDeviceId": int(action_device_dd.value) if action_device_dd.value else None,
                    "actionTargetIsOn": True if action_state_dd.value == "on" else False,
                    "actionSceneId": int(action_scene_dd.value) if action_scene_dd.value else None,
                }
                if editing:
                    api_request("put", f"/api/rules/{rule['id']}", payload)
                    message = "Правило обновлено"
                else:
                    api_request("post", "/api/rules", payload)
                    message = "Правило создано"
                close_dialog(dialog)
                refresh_all()
                build()
                show_message(message)
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Изменить правило" if editing else "Создать правило", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=760,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        name_tf,
                        description_tf,
                        enabled_sw,
                        ft.Row(spacing=10, controls=[trigger_device_dd, event_type_tf]),
                        ft.Row(spacing=10, controls=[operator_dd, compare_tf]),
                        ft.Row(spacing=10, controls=[action_kind_dd, action_state_dd]),
                        ft.Row(spacing=10, controls=[action_device_dd, action_scene_dd]),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Сохранить", on_click=save),
            ],
        )
        show_dialog(dialog)

    def delete_rule(rule_id: int, rule_name: str):
        def action():
            try:
                api_request("delete", f"/api/rules/{rule_id}")
                refresh_all()
                build()
                show_message(f"Правило удалено: {rule_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить правило", f"Удалить правило «{rule_name}»?", action)

    def set_rule_enabled(rule_id: int, is_enabled: bool):
        try:
            api_request("put", f"/api/rules/{rule_id}/enabled", {"isEnabled": is_enabled})
            refresh_all()
            build()
            show_message("Состояние правила обновлено")
        except Exception as ex:
            show_message(str(ex))

    def open_schedule_dialog(schedule: dict[str, Any] | None = None):
        editing = schedule is not None
        name_tf = field(label="Название расписания", value=(schedule or {}).get("name", ""))
        description_tf = field(label="Описание", value=(schedule or {}).get("description", ""), multiline=True, min_lines=2, max_lines=3)
        time_tf = field(label="Время HH:mm", value=(schedule or {}).get("timeOfDay", "08:00"))
        enabled_sw = ft.Switch(label="Расписание активно", value=bool((schedule or {}).get("isEnabled", True)))
        action_kind_dd = dropdown(label="Тип действия", value=(schedule or {}).get("actionKind", "device_state"), options=[ft.dropdown.Option(x, action_kind_title(x)) for x in action_kinds()])
        action_device_dd = dropdown(label="Целевое устройство", value=str(schedule.get("actionDeviceId")) if editing and schedule.get("actionDeviceId") is not None else None, options=device_options())
        action_state_dd = dropdown(
            label="Целевое состояние",
            value="on" if (schedule or {}).get("actionTargetIsOn", True) else "off",
            options=[ft.dropdown.Option("on", "Включить"), ft.dropdown.Option("off", "Выключить")],
        )
        action_scene_dd = dropdown(label="Или сценарий", value=str(schedule.get("actionSceneId")) if editing and schedule.get("actionSceneId") is not None else None, options=scene_options())

        selected_days = set((schedule or {}).get("daysOfWeek", [1, 2, 3, 4, 5]))
        day_boxes: list[tuple[int, ft.Checkbox]] = []
        for item in schedule_days():
            box = ft.Checkbox(label=str(item.get("title")), value=int(item.get("value")) in selected_days)
            day_boxes.append((int(item.get("value")), box))

        def save(_):
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "description": (description_tf.value or "").strip(),
                    "isEnabled": bool(enabled_sw.value),
                    "timeOfDay": (time_tf.value or "").strip(),
                    "daysOfWeek": [value for value, box in day_boxes if box.value],
                    "actionKind": action_kind_dd.value or "device_state",
                    "actionDeviceId": int(action_device_dd.value) if action_device_dd.value else None,
                    "actionTargetIsOn": True if action_state_dd.value == "on" else False,
                    "actionSceneId": int(action_scene_dd.value) if action_scene_dd.value else None,
                }
                if editing:
                    api_request("put", f"/api/schedules/{schedule['id']}", payload)
                    message = "Расписание обновлено"
                else:
                    api_request("post", "/api/schedules", payload)
                    message = "Расписание создано"
                close_dialog(dialog)
                refresh_all()
                build()
                show_message(message)
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Изменить расписание" if editing else "Создать расписание", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=760,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        name_tf,
                        description_tf,
                        ft.Row(spacing=10, controls=[time_tf, enabled_sw]),
                        T("Дни недели", weight=ft.FontWeight.BOLD),
                        ft.Row(spacing=8, controls=[box for _, box in day_boxes]),
                        ft.Row(spacing=10, controls=[action_kind_dd, action_state_dd]),
                        ft.Row(spacing=10, controls=[action_device_dd, action_scene_dd]),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Сохранить", on_click=save),
            ],
        )
        show_dialog(dialog)

    def delete_schedule(schedule_id: int, schedule_name: str):
        def action():
            try:
                api_request("delete", f"/api/schedules/{schedule_id}")
                refresh_all()
                build()
                show_message(f"Расписание удалено: {schedule_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить расписание", f"Удалить расписание «{schedule_name}»?", action)

    def set_schedule_enabled(schedule_id: int, is_enabled: bool):
        try:
            api_request("put", f"/api/schedules/{schedule_id}/enabled", {"isEnabled": is_enabled})
            refresh_all()
            build()
            show_message("Состояние расписания обновлено")
        except Exception as ex:
            show_message(str(ex))

    def run_due_schedules():
        try:
            result = api_request("post", "/api/schedules/run-due") or {}
            refresh_all()
            build()
            show_message(str(result.get("message", "Проверка расписаний выполнена")))
        except Exception as ex:
            show_message(str(ex))

    def open_event_dialog():
        source_device_dd = dropdown(label="Источник события", options=device_options(sensor_first=True))
        event_type_tf = field(label="Тип события", value="motion")
        value_tf = field(label="Значение", value="true")
        message_tf = field(label="Сообщение", value="Тестовое событие")

        def send_event(_):
            try:
                result = api_request(
                    "post",
                    "/api/events",
                    {
                        "deviceId": int(source_device_dd.value or 0),
                        "eventType": (event_type_tf.value or "").strip(),
                        "value": (value_tf.value or "").strip(),
                        "message": (message_tf.value or "").strip(),
                    },
                ) or {}
                close_dialog(dialog)
                refresh_all()
                build()
                count = len(result.get("triggeredRules", []) or [])
                show_message(f"Событие отправлено. Сработало правил: {count}")
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Отправить событие датчика", weight=ft.FontWeight.BOLD),
            content=ft.Column(tight=True, spacing=10, controls=[source_device_dd, event_type_tf, value_tf, message_tf]),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Отправить", on_click=send_event),
            ],
        )
        show_dialog(dialog)

    def home_view() -> ft.Control:
        recent_logs = data["logs"][:6]
        log_controls = [
            card(
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[T(str(log.get("message", "Событие")), weight=ft.FontWeight.BOLD), TM(fmt_dt(log.get("ts")), size=12)],
                ),
                TM(f"Источник: {log.get('source', 'api')} · Тип: {log.get('eventType', 'EVENT')}", size=12),
            )
            for log in recent_logs
        ] or [card(TM("История пока пустая"))]

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
                                "Устройства теперь можно подключать как реальные: с идентификатором, провайдером, протоколом, тестом связи, правилами и расписаниями.",
                                color="#e0e7ff",
                            ),
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.ElevatedButton("Добавить устройство", icon=ft.Icons.ADD, on_click=lambda e: open_device_dialog()),
                                    ft.OutlinedButton("Отправить событие", icon=ft.Icons.SENSORS, on_click=lambda e: open_event_dialog()),
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
                ft.Row(
                    spacing=12,
                    controls=[
                        stat_card("Правила", str(len(data["rules"])), ft.Icons.RULE, 4),
                        stat_card("Расписания", str(len(data["schedules"])), ft.Icons.SCHEDULE, 5),
                        stat_card("Логи", str(len(data["logs"])), ft.Icons.HISTORY, 6),
                    ],
                ),
                T("Последние события", size=18, weight=ft.FontWeight.BOLD),
                *log_controls,
            ],
        )

    def devices_view() -> ft.Control:
        device_cards = []
        for device in data["devices"]:
            room_dd = dropdown(value=str(device.get("roomId")) if device.get("roomId") is not None else None, options=room_options(), width=220)
            device_cards.append(
                card(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    T(str(device.get("name", "Устройство")), size=18, weight=ft.FontWeight.BOLD),
                                    TM(f"ID: {device.get('externalId', '—')} · Комната: {device.get('room', 'Не указана')}", size=12),
                                    TM(f"Тип: {device.get('type', 'Другое')} · {provider_title(device.get('provider'))}", size=12),
                                    TM(f"Протокол: {device.get('protocol', 'manual')} · Канал: {device.get('channel', 'local')}", size=12),
                                    TM(device.get("connectionMessage") or "", size=12),
                                ],
                            ),
                            ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                controls=[
                                    status_chip(str(device.get("connectionStatus", "unknown")), device.get("connectionStatus")),
                                    bool_chip(bool(device.get("isOn"))),
                                ],
                            ),
                        ],
                    ),
                    TM(f"Последняя проверка: {fmt_dt(device.get('lastConnectionCheckAt'))} · Последний сигнал: {fmt_dt(device.get('lastSeenAt'))}"),
                    ft.Row(
                        spacing=10,
                        controls=[
                            ft.ElevatedButton("Toggle", icon=ft.Icons.POWER_SETTINGS_NEW, on_click=lambda e, device_id=device["id"]: toggle_device(device_id)),
                            ft.OutlinedButton("Изменить", icon=ft.Icons.EDIT_OUTLINED, on_click=lambda e, d=device: open_device_dialog(d)),
                            ft.OutlinedButton("Удалить", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e, d=device: delete_device(int(d["id"]), str(d.get("name", "Устройство")))),
                        ],
                    ),
                    ft.Row(
                        spacing=10,
                        controls=[
                            room_dd,
                            ft.OutlinedButton("Переместить", icon=ft.Icons.SWAP_HORIZ, on_click=lambda e, device_id=device["id"], dd=room_dd: move_device(int(device_id), dd.value)),
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
                        ft.Column(spacing=4, controls=[T("Устройства", size=22, weight=ft.FontWeight.BOLD), TM("Подключение реальных устройств, тест связи и управление")]),
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Добавить", icon=ft.Icons.ADD, on_click=lambda e: open_device_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()))]),
                    ],
                ),
                *(device_cards or [card(TM("Устройств пока нет"))]),
            ],
        )

    def rooms_view() -> ft.Control:
        devices_by_room: dict[int, list[dict[str, Any]]] = {}
        for device in data["devices"]:
            room_id = device.get("roomId")
            if room_id is None:
                continue
            devices_by_room.setdefault(int(room_id), []).append(device)

        room_cards = []
        for room in data["rooms"]:
            room_devices = devices_by_room.get(int(room["id"]), [])
            room_cards.append(
                card(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(spacing=4, controls=[T(str(room.get("name", "Комната")), size=18, weight=ft.FontWeight.BOLD), TM(f"Зона: {room.get('zone', '') or 'Не указана'}", size=12), TM(f"Устройств: {room.get('deviceCount', 0)}", size=12)]),
                            ft.Row(spacing=8, controls=[ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, r=room: open_room_dialog(r)), ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, r=room: delete_room(int(r["id"]), str(r.get("name", "Комната"))))]),
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
                                    ft.Column(spacing=2, controls=[T(str(device.get("name", "Устройство")), weight=ft.FontWeight.BOLD), TM(f"Тип: {device.get('type', 'Другое')} · {device.get('externalId', '—')}", size=12)]),
                                    status_chip(str(device.get("connectionStatus", "unknown")), device.get("connectionStatus")),
                                ],
                            ),
                        )
                        for device in room_devices
                    ] if room_devices else [TM("В этой комнате пока нет устройств")]),
                )
            )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Комнаты и зоны", size=22, weight=ft.FontWeight.BOLD), TM("CRUD комнат и группировка устройств")]),
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать комнату", icon=ft.Icons.ADD, on_click=lambda e: open_room_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()))]),
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
                            ft.Column(spacing=4, controls=[T(str(scene.get("name", "Сценарий")), size=18, weight=ft.FontWeight.BOLD), TM(str(scene.get("description", "")) or "Без описания", size=12)]),
                            ft.Row(spacing=8, controls=[ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, s=scene: open_scene_dialog(s)), ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, s=scene: delete_scene(int(s["id"]), str(s.get("name", "Сценарий"))))]),
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
                                    ft.Column(spacing=2, controls=[T(str(action.get("deviceName", "Устройство")), weight=ft.FontWeight.BOLD), TM(str(action.get("roomName", "Комната не указана")), size=12)]),
                                    TM("Включить" if action.get("targetIsOn") else "Выключить", size=12),
                                ],
                            ),
                        )
                        for action in action_lines
                    ] if action_lines else [TM("В сценарии пока нет действий")]),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(spacing=2, controls=[TM(f"Последний запуск: {fmt_dt(scene.get('lastRunAt'))}", size=12), TM(f"Статус: {scene.get('lastRunStatus') or 'не запускался'}", size=12), TM(scene.get("lastRunMessage") or "", size=12)]),
                            ft.ElevatedButton("Запустить", icon=ft.Icons.PLAY_ARROW, on_click=lambda e, s=scene: run_scene(int(s["id"]), str(s.get("name", "Сценарий")))),
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
                        ft.Column(spacing=4, controls=[T("Сценарии", size=22, weight=ft.FontWeight.BOLD), TM("Ручные сценарии, которые могут запускаться и из правил, и по расписанию")]),
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать сценарий", icon=ft.Icons.AUTO_AWESOME, on_click=lambda e: open_scene_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()))]),
                    ],
                ),
                *(scene_cards or [card(TM("Сценариев пока нет"))]),
            ],
        )

    def rules_view() -> ft.Control:
        rule_cards = []
        for rule in data["rules"]:
            if rule.get("actionKind") == "scene_run":
                action_text = f"Запустить сценарий: {rule.get('actionSceneName', '—')}"
            else:
                action_text = f"Устройство: {rule.get('actionDeviceName', '—')} -> {'ON' if rule.get('actionTargetIsOn') else 'OFF'}"
            rule_cards.append(
                card(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(spacing=4, controls=[T(str(rule.get("name", "Правило")), size=18, weight=ft.FontWeight.BOLD), TM(str(rule.get("description", "")) or "Без описания", size=12), TM(f"Если {rule.get('triggerDeviceName', 'датчик')} / {rule.get('triggerEventType', 'event')} {rule.get('comparisonOperator', '=')} {rule.get('compareValue', '')}", size=12)]),
                            ft.Row(spacing=8, controls=[status_chip("Активно" if rule.get("isEnabled") else "Выключено", "enabled" if rule.get("isEnabled") else "disabled"), ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, r=rule: open_rule_dialog(r)), ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, r=rule: delete_rule(int(r["id"]), str(r.get("name", "Правило"))))]),
                        ],
                    ),
                    TM(action_text, size=12),
                    TM(f"Последнее срабатывание: {fmt_dt(rule.get('lastTriggeredAt'))}", size=12),
                    TM(rule.get("lastTriggerMessage") or "", size=12),
                    ft.Row(spacing=10, controls=[ft.ElevatedButton("Включить" if not rule.get("isEnabled") else "Выключить", icon=ft.Icons.TOGGLE_ON if rule.get("isEnabled") else ft.Icons.TOGGLE_OFF, on_click=lambda e, rid=rule["id"], enabled=not bool(rule.get("isEnabled")): set_rule_enabled(int(rid), enabled)), ft.OutlinedButton("Тест событием", icon=ft.Icons.SENSORS, on_click=lambda e: open_event_dialog())]),
                )
            )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Правила", size=22, weight=ft.FontWeight.BOLD), TM("Если событие датчика подходит под условие, выполняется действие или сценарий")]),
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать правило", icon=ft.Icons.ADD, on_click=lambda e: open_rule_dialog()), ft.OutlinedButton("Отправить событие", icon=ft.Icons.SENSORS, on_click=lambda e: open_event_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()))]),
                    ],
                ),
                *(rule_cards or [card(TM("Правил пока нет"))]),
            ],
        )

    def schedules_view() -> ft.Control:
        schedule_cards = []
        for schedule in data["schedules"]:
            if schedule.get("actionKind") == "scene_run":
                action_text = f"Запустить сценарий: {schedule.get('actionSceneName', '—')}"
            else:
                action_text = f"Устройство: {schedule.get('actionDeviceName', '—')} -> {'ON' if schedule.get('actionTargetIsOn') else 'OFF'}"
            schedule_cards.append(
                card(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(spacing=4, controls=[T(str(schedule.get("name", "Расписание")), size=18, weight=ft.FontWeight.BOLD), TM(str(schedule.get("description", "")) or "Без описания", size=12), TM(f"Время: {schedule.get('timeOfDay', '—')} · Дни: {schedule_days_title(schedule.get('daysOfWeek'))}", size=12)]),
                            ft.Row(spacing=8, controls=[status_chip("Активно" if schedule.get("isEnabled") else "Выключено", "enabled" if schedule.get("isEnabled") else "disabled"), ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, s=schedule: open_schedule_dialog(s)), ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, s=schedule: delete_schedule(int(s["id"]), str(s.get("name", "Расписание"))))]),
                        ],
                    ),
                    TM(action_text, size=12),
                    TM(f"Последний запуск: {fmt_dt(schedule.get('lastRunAt'))}", size=12),
                    TM(schedule.get("lastRunMessage") or "", size=12),
                    ft.Row(spacing=10, controls=[ft.ElevatedButton("Включить" if not schedule.get("isEnabled") else "Выключить", icon=ft.Icons.TOGGLE_ON if schedule.get("isEnabled") else ft.Icons.TOGGLE_OFF, on_click=lambda e, sid=schedule["id"], enabled=not bool(schedule.get("isEnabled")): set_schedule_enabled(int(sid), enabled)), ft.OutlinedButton("Проверить сейчас", icon=ft.Icons.SCHEDULE, on_click=lambda e: run_due_schedules())]),
                )
            )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Расписание", size=22, weight=ft.FontWeight.BOLD), TM("Автоматический запуск действий и сценариев по времени")]),
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать расписание", icon=ft.Icons.ADD, on_click=lambda e: open_schedule_dialog()), ft.OutlinedButton("Проверить сейчас", icon=ft.Icons.SCHEDULE, on_click=lambda e: run_due_schedules()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()))]),
                    ],
                ),
                *(schedule_cards or [card(TM("Расписаний пока нет"))]),
            ],
        )

    def history_view() -> ft.Control:
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("История и логирование", size=22, weight=ft.FontWeight.BOLD), TM("Логи backend, правила, расписания и результаты сценариев")]),
                        ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build())),
                    ],
                ),
                *([
                    card(
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[T(str(log.get("message", "Событие")), weight=ft.FontWeight.BOLD), TM(fmt_dt(log.get("ts")), size=12)]),
                        TM(f"Тип: {log.get('eventType', 'EVENT')} · Источник: {log.get('source', 'api')}", size=12),
                        TM(f"deviceId={log.get('deviceId')} · sceneId={log.get('sceneId')} · runId={log.get('runId')}", size=12),
                    )
                    for log in data["logs"]
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
                card(T("Интерфейс", weight=ft.FontWeight.BOLD), dark_sw, ft.ElevatedButton("Сохранить", on_click=save_settings)),
                card(T("Подключение к API", weight=ft.FontWeight.BOLD), TM(f"Base URL: {API_BASE}"), TM("Основной backend должен быть запущен из backend/CalHouse.Api"), TM("Flet UI работает поверх ASP.NET Core API, а не через отдельный python_api слой")),
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
            ft.NavigationBarDestination(icon=ft.Icons.RULE, selected_icon=ft.Icons.RULE, label="Правила"),
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
        page.appbar = ft.AppBar(bgcolor=c("nav"), title=ft.Text("CALHouse", color=c("text"), weight=ft.FontWeight.BOLD), actions=[ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: (refresh_all(True), build()), icon_color=c("text"))])
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
