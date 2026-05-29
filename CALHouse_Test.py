import flet as ft
import asyncio
import httpx
from datetime import datetime
from typing import Any
import validation as validators

API_BASE = "http://localhost:5000"
API_TIMEOUT_SECONDS = 3.0
DEBUG_DEVICE_FORM = False
DEFAULT_DEVICE_TYPES = [
    {"code": "light", "displayName": "Свет", "capabilities": {"canToggle": True}, "allowedProviders": ["mock"]},
    {"code": "socket", "displayName": "Розетка", "capabilities": {"canToggle": True}, "allowedProviders": ["mock"]},
    {"code": "relay", "displayName": "Реле", "capabilities": {"canToggle": True}, "allowedProviders": ["mock"]},
    {"code": "motion_sensor", "displayName": "Датчик движения", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
    {"code": "temperature_sensor", "displayName": "Датчик температуры", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
    {"code": "thermostat", "displayName": "Термостат", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
    {"code": "camera", "displayName": "Камера", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
    {"code": "generic", "displayName": "Другое", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
]
DEFAULT_PROVIDERS = [
    {
        "code": "mock",
        "key": "mock",
        "displayName": "Локальный тестовый режим",
        "title": "Локальный тестовый режим",
        "protocol": "manual",
        "channel": "local",
        "note": "Локальный тестовый режим: сетевые параметры не нужны, команда не отправляется на реальное устройство.",
        "formFields": [],
    }
]
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

CONNECTION_FIELD_LABELS = {
    "host": "Host / IP",
    "port": "Port",
    "url": "URL",
    "path": "Path",
    "topic": "Topic",
    "entity_id": "Entity ID",
    "state_topic": "Topic состояния",
    "username": "Пользователь",
    "password": "Пароль / ключ устройства",
    "device_key": "Пароль / ключ устройства",
    "token": "Токен",
    "method": "HTTP-метод",
    "headers": "Заголовки JSON",
    "body_template": "Шаблон body",
    "snapshot_url": "URL снимка",
    "payload_template": "Шаблон payload",
}


def fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


async def main(page: ft.Page):
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
                "bg": "#191b21",
                "card": "#272b33",
                "border": "#181c24",
                "text": "#f8fafc",
                "muted": "#94a3b8",
                "field": "#4a4a4a",
                "nav": "#ffffff",
                "accent": "#14b385",
            }
        return {
            "bg": "#f3f4f6",
            "card": "#ffffff",
            "border": "#e5e7eb",
            "text": "#0f172a",
            "muted": "#64748b",
            "field": "#eef2f7",
            "nav": "#ffffff",
            "accent": "#14b385",
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

    async def api_request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = API_TIMEOUT_SECONDS):
        url = f"{API_BASE}{path}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method=method.upper(), url=url, json=payload)
            if response.status_code >= 400:
                print(f"[api:error] status_code={response.status_code}", flush=True)
                print(f"[api:error] response.text={response.text}", flush=True)
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {}
                message = error_data.get("message") or error_data.get("error") or f"HTTP {response.status_code}"
                error_details = error_data.get("errors") or error_data.get("validationErrors") or error_data.get("details")
                if error_details:
                    if isinstance(error_details, dict):
                        parts = []
                        for key, value in error_details.items():
                            if isinstance(value, list):
                                value_text = ", ".join(str(item) for item in value)
                            else:
                                value_text = str(value)
                            parts.append(f"{key}: {value_text}")
                        details_text = "; ".join(parts)
                    elif isinstance(error_details, list):
                        details_text = "; ".join(str(item) for item in error_details)
                    else:
                        details_text = str(error_details)
                    if details_text:
                        message = f"{message}: {details_text}"
                raise RuntimeError(message)
            if not response.text:
                return None
            return response.json()
        except httpx.TimeoutException as ex:
            raise RuntimeError("Сервер долго не отвечает или устройство не ответило") from ex
        except httpx.RequestError as ex:
            raise RuntimeError(f"API недоступен: {ex}") from ex

    def require_text(value: Any, label: str, max_length: int = 80) -> str:
        return validators.require_safe_text(value, label, 2, max_length)

    def optional_text(value: Any, label: str, max_length: int = 500) -> str:
        return validators.optional_free_text(value, label, max_length)

    def require_selected(value: Any, label: str, allowed: set[str] | None = None) -> str:
        return validators.require_selected(value, label, allowed)

    def require_external_id(value: Any) -> str:
        return validators.require_identifier(value, "Идентификатор")

    def require_code_value(value: Any, label: str, max_length: int = 80) -> str:
        return validators.require_code(value, label, max_length)

    def require_hhmm(value: Any) -> str:
        return validators.require_hhmm(value)

    def validate_connection_values(connection: dict[str, str], schema_fields: dict[str, dict[str, Any]] | None = None):
        validators.validate_connection_values(connection, schema_fields)

    def validate_control(control: ft.Control, validator) -> bool:
        try:
            validator(getattr(control, "value", None))
            if hasattr(control, "error_text"):
                control.error_text = None
            ok = True
        except Exception as ex:
            if hasattr(control, "error_text"):
                control.error_text = str(ex)
            ok = False
        try:
            if getattr(control, "page", None):
                control.update()
        except Exception:
            pass
        return ok

    def bind_live_validator(control: ft.Control, validator):
        def on_change(e):
            validate_control(e.control, validator)

        control.on_change = on_change
        return control

    def bind_digits_only(control: ft.TextField, validator):
        def on_change(e):
            raw = str(e.control.value or "")
            digits = "".join(ch for ch in raw if ch.isdigit())
            if raw != digits:
                e.control.value = digits
            validate_control(e.control, validator)

        control.on_change = on_change
        return control

    def ensure_controls_valid(items: list[tuple[ft.Control, Any]]):
        first_error = None
        for control, validator in items:
            if not validate_control(control, validator) and first_error is None:
                first_error = getattr(control, "error_text", None)
        if first_error:
            raise ValueError(first_error)

    async def load_catalog(show_error: bool = False):
        try:
            data["catalog"] = await api_request("get", "/api/device-catalog") or {}
        except Exception as ex:
            data["catalog"] = {}
            if show_error:
                show_message(str(ex))

    async def load_devices(show_error: bool = False):
        try:
            items = await api_request("get", "/api/devices") or []
            data["devices"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    async def load_rooms(show_error: bool = False):
        try:
            items = await api_request("get", "/api/rooms") or []
            data["rooms"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    async def load_scenes(show_error: bool = False):
        try:
            items = await api_request("get", "/api/scenes") or []
            data["scenes"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    async def load_rules(show_error: bool = False):
        try:
            items = await api_request("get", "/api/rules") or []
            data["rules"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    async def load_schedules(show_error: bool = False):
        try:
            items = await api_request("get", "/api/schedules") or []
            data["schedules"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    async def load_logs(show_error: bool = False):
        try:
            items = await api_request("get", "/api/logs?limit=80") or []
            data["logs"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(str(ex))

    async def refresh_all(show_toast: bool = False):
        await asyncio.gather(
            load_catalog(show_error=True),
            load_rooms(show_error=True),
            load_devices(show_error=True),
            load_scenes(show_error=True),
            load_rules(show_error=True),
            load_schedules(show_error=True),
            load_logs(show_error=True),
        )
        if show_toast:
            show_message("Данные обновлены")

    async def refresh_sections(*sections: str, show_toast: bool = False):
        tasks = []
        if "catalog" in sections:
            tasks.append(load_catalog(show_error=True))
        if "rooms" in sections:
            tasks.append(load_rooms(show_error=True))
        if "devices" in sections:
            tasks.append(load_devices(show_error=True))
        if "scenes" in sections:
            tasks.append(load_scenes(show_error=True))
        if "rules" in sections:
            tasks.append(load_rules(show_error=True))
        if "schedules" in sections:
            tasks.append(load_schedules(show_error=True))
        if "logs" in sections:
            tasks.append(load_logs(show_error=True))
        if tasks:
            await asyncio.gather(*tasks)
        if show_toast:
            show_message("Данные обновлены")

    async def refresh_and_build(*sections: str, show_toast: bool = False):
        if sections:
            await refresh_sections(*sections, show_toast=show_toast)
        else:
            await refresh_all(show_toast=show_toast)
        build()

    def async_click(handler):
        async def wrapper(e):
            result = handler(e)
            if asyncio.iscoroutine(result):
                return await result
            return result

        return wrapper

    async def run_button_action(e, action, busy_text: str = "Выполняется..."):
        control = getattr(e, "control", None)
        old_disabled = getattr(control, "disabled", None) if control is not None else None
        old_text = getattr(control, "text", None) if control is not None and hasattr(control, "text") else None
        try:
            if control is not None:
                if hasattr(control, "disabled"):
                    control.disabled = True
                if old_text is not None:
                    control.text = busy_text
                try:
                    control.update()
                except Exception:
                    page.update()
            result = action()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as ex:
            show_message(str(ex))
        finally:
            if control is not None:
                if old_disabled is not None and hasattr(control, "disabled"):
                    control.disabled = old_disabled
                if old_text is not None:
                    control.text = old_text
                try:
                    control.update()
                except Exception:
                    page.update()

    def device_type_defs() -> list[dict[str, Any]]:
        items = data["catalog"].get("deviceTypes") or DEFAULT_DEVICE_TYPES
        if not isinstance(items, list):
            return DEFAULT_DEVICE_TYPES
        result: list[dict[str, Any]] = []
        for item in items:
            if isinstance(item, dict):
                result.append(item)
            else:
                value = str(item)
                result.append({"code": value, "displayName": value, "capabilities": {"canToggle": True}, "allowedProviders": []})
        return result

    def device_type_code(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "generic"
        lowered = raw.lower()
        for item in device_type_defs():
            candidates = [item.get("code"), item.get("displayName"), *(item.get("legacyNames") or [])]
            if any(str(candidate or "").lower() == lowered for candidate in candidates):
                return str(item.get("code", raw))
        return raw

    def device_types() -> list[str]:
        return [str(item.get("code", "")) for item in device_type_defs()]

    def device_type_title(code: Any) -> str:
        normalized = device_type_code(code)
        for item in device_type_defs():
            if str(item.get("code", "")) == normalized:
                return str(item.get("displayName", normalized))
        return normalized

    def device_type_capabilities(code: Any) -> dict[str, Any]:
        normalized = device_type_code(code)
        for item in device_type_defs():
            if str(item.get("code", "")) == normalized:
                capabilities = item.get("capabilities") or {}
                return capabilities if isinstance(capabilities, dict) else {}
        return {}

    def providers() -> list[dict[str, Any]]:
        items = data["catalog"].get("providers") or DEFAULT_PROVIDERS
        return items if isinstance(items, list) else DEFAULT_PROVIDERS

    def provider_map() -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in providers():
            keys = [item.get("code"), item.get("key"), *(item.get("legacyKeys") or [])]
            for key in keys:
                if key:
                    result[str(key)] = item
        return result

    def provider_code(value: Any) -> str:
        raw = str(value or "mock").strip()
        lowered = raw.lower()
        for item in providers():
            candidates = [item.get("code"), item.get("key"), *(item.get("legacyKeys") or [])]
            if any(str(candidate or "").lower() == lowered for candidate in candidates):
                return str(item.get("code", item.get("key", raw)))
        return raw

    def providers_for_type(type_code: Any) -> list[dict[str, Any]]:
        normalized = device_type_code(type_code)
        type_def = next((item for item in device_type_defs() if str(item.get("code", "")) == normalized), None)
        allowed = {provider_code(x) for x in ((type_def or {}).get("allowedProviders") or [])}
        if not allowed:
            return providers()
        return [item for item in providers() if provider_code(item.get("code", item.get("key", ""))) in allowed]

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
            sensor_types = {"motion_sensor", "temperature_sensor"}
            items = sorted(items, key=lambda item: (0 if device_type_code(item.get("type")) in sensor_types else 1, str(item.get("name", ""))))
            return [ft.dropdown.Option(str(device["id"]), device["name"]) for device in items]
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
        code = provider_code(key)
        item = provider_map().get(code)
        return str(item.get("displayName", item.get("title", code))) if item else str(key)

    def provider_option(provider: dict[str, Any]) -> ft.dropdown.Option:
        code = provider_code(provider.get("code", provider.get("key", "mock")))
        title = str(provider.get("displayName", provider.get("title", code)))
        return ft.dropdown.Option(code, title)

    def provider_form_fields(provider: dict[str, Any]) -> list[dict[str, Any]]:
        form_fields = provider.get("formFields")
        if isinstance(form_fields, list) and form_fields:
            return [item for item in form_fields if isinstance(item, dict)]

        required = [str(name) for name in (provider.get("requiredFields") or [])]
        optional = [str(name) for name in (provider.get("optionalFields") or [])]
        fields: list[dict[str, Any]] = []
        seen: set[str] = set()
        for name in [*required, *optional]:
            if name in seen:
                continue
            seen.add(name)
            fields.append(
                {
                    "name": name,
                    "label": CONNECTION_FIELD_LABELS.get(name, name),
                    "kind": "password" if name in {"password", "device_key", "token"} else "text",
                    "required": name in required,
                }
            )
        return fields

    def action_kind_title(kind: str | None) -> str:
        if kind == "device_state":
            return "Изменить устройство"
        if kind == "scene_run":
            return "Запустить сценарий"
        return str(kind or "—")

    def device_can_receive_commands(device: dict[str, Any]) -> bool:
        capabilities = device_type_capabilities(device.get("type"))
        return bool(capabilities.get("canReceiveCommands", capabilities.get("canToggle", True)) or capabilities.get("canToggle", False))

    def find_device_by_id(device_id: Any) -> dict[str, Any] | None:
        try:
            target_id = int(device_id)
        except (TypeError, ValueError):
            return None
        return next((item for item in data["devices"] if int(item.get("id", 0)) == target_id), None)

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

        async def on_yes(e):
            nonlocal dialog_ref
            if dialog_ref is not None:
                close_dialog(dialog_ref)
            result = action()
            if asyncio.iscoroutine(result):
                await result

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

    async def open_device_dialog(device: dict[str, Any] | None = None):
        await load_catalog(show_error=True)
        editing = device is not None
        catalog_is_loaded = bool(data["catalog"].get("providers")) and bool(data["catalog"].get("deviceTypes"))
        if not catalog_is_loaded:
            show_message("Каталог провайдеров не загружен. Доступен только локальный тестовый режим.")
        selected_type = device_type_code((device or {}).get("type", "generic"))
        provider_key = provider_code((device or {}).get("provider", "mock") or "mock")

        name_tf = field(label="Название", value=(device or {}).get("name", ""), hint_text="Например: Лампа IKEA")
        external_id_tf = field(label="Идентификатор", value=(device or {}).get("externalId", ""), hint_text="Например: kitchen-light-01")
        manufacturer_tf = field(label="Производитель", value=(device or {}).get("manufacturer", ""))
        model_tf = field(label="Модель", value=(device or {}).get("model", ""))
        type_dd = dropdown(label="Тип устройства", value=selected_type, options=[ft.dropdown.Option(item.get("code"), item.get("displayName")) for item in device_type_defs()])
        provider_dd = dropdown(label="Провайдер", value=provider_key, options=[provider_option(item) for item in providers_for_type(selected_type)])
        protocol_tf = field(label="Протокол", value=str((device or {}).get("protocol", "manual")))
        channel_tf = field(label="Канал", value=str((device or {}).get("channel", "local")))
        room_dd = dropdown(label="Комната из списка", value=str(device.get("roomId")) if editing and device.get("roomId") is not None else None, options=room_options())
        new_room_tf = field(label="Или новая комната", value="" if editing else (device or {}).get("room", ""), hint_text="Оставь пустым, если выбрал комнату выше")
        is_on_sw = ft.Switch(label="Включить сразу", value=bool((device or {}).get("isOn", False)))

        bind_live_validator(name_tf, lambda value: validators.require_safe_text(value, "Название", 2, 80))
        bind_live_validator(external_id_tf, validators.require_identifier)
        bind_live_validator(manufacturer_tf, lambda value: validators.optional_safe_text(value, "Производитель", 2, 50))
        bind_live_validator(model_tf, lambda value: validators.optional_safe_text(value, "Модель", 1, 80))
        bind_live_validator(channel_tf, lambda value: validators.optional_code(value, "Канал", 50))
        bind_live_validator(new_room_tf, lambda value: validators.optional_safe_text(value, "Новая комната", 2, 50, no_only_digits=True))

        existing_conn = (device or {}).get("connection", {}) or {}
        connection_controls: dict[str, ft.TextField] = {}
        connection_fields_column = ft.Column(spacing=10, controls=[])
        note_text = TM("", size=12)
        form_status_text = TM("", size=12, color="#92400e")
        test_result = TM("", size=12)
        active_schema_names: set[str] = set()
        active_schema_defs: dict[str, dict[str, Any]] = {}

        def debug_device_form(stage: str, **values: Any):
            if not DEBUG_DEVICE_FORM:
                return
            parts = [f"{key}={value!r}" for key, value in values.items()]
            print(f"[device-form:{stage}] " + " ".join(parts), flush=True)

        def event_value(e: ft.ControlEvent, fallback: Any) -> Any:
            data_value = getattr(e, "data", None)
            if data_value is not None and str(data_value).strip():
                return data_value
            control = getattr(e, "control", None)
            control_value = getattr(control, "value", None)
            if control_value is not None and str(control_value).strip():
                return control_value
            return fallback

        def resolve_provider_code(value: Any) -> str:
            raw = str(value or "").strip()
            for option in (provider_dd.options or []):
                option_key = str(getattr(option, "key", "") or "")
                option_text = str(getattr(option, "text", "") or "")
                if raw and raw in {option_key, option_text}:
                    return provider_code(option_key or raw)
            return provider_code(raw)

        def update_dynamic_form_controls():
            for control in [type_dd, provider_dd, protocol_tf, channel_tf, note_text, form_status_text, is_on_sw, connection_fields_column]:
                try:
                    if getattr(control, "page", None):
                        control.update()
                except Exception:
                    pass
            try:
                if getattr(dialog.content, "page", None):
                    dialog.content.update()
            except Exception:
                pass
            try:
                if getattr(dialog, "page", None):
                    dialog.update()
            except Exception:
                pass
            page.update()

        def sync_provider_options(type_code: Any, preferred_provider: Any | None = None, source: str = "sync"):
            provider_before = provider_dd.value
            options = providers_for_type(type_code)
            all_providers = {
                resolve_provider_code(item.get("code", item.get("key", "mock"))): item
                for item in providers()
            }
            requested = resolve_provider_code(preferred_provider if preferred_provider is not None else provider_dd.value)
            option_codes = [resolve_provider_code(item.get("code", item.get("key", "mock"))) for item in options]
            provider_dd.options = [provider_option(item) for item in options]
            allowed = option_codes
            fallback_used = False

            if requested in allowed:
                selected = requested
            elif allowed:
                selected = allowed[0]
                fallback_used = True
            elif requested in all_providers:
                selected = requested
            else:
                selected = "mock"
                fallback_used = True

            provider_dd.value = selected
            provider = all_providers.get(selected)
            if provider is None and options:
                provider = options[0]
                provider_dd.value = resolve_provider_code(provider.get("code", provider.get("key", "mock")))
                fallback_used = True
            if provider is None:
                fallback_used = True
            selected_provider = resolve_provider_code((provider or DEFAULT_PROVIDERS[0]).get("code", (provider or DEFAULT_PROVIDERS[0]).get("key", "mock")))
            debug_device_form(
                "sync_provider_options",
                source=source,
                type=type_code,
                preferred_provider=preferred_provider,
                provider_before=provider_before,
                requested=requested,
                provider_after=provider_dd.value,
                allowed=allowed,
                selected_provider=selected_provider,
                fallback_used=fallback_used,
            )
            return provider or DEFAULT_PROVIDERS[0], allowed, fallback_used

        def existing_connection_value(name: str) -> str:
            if name == "password":
                return str(existing_conn.get("password", existing_conn.get("device_key", "")) or "")
            if name == "device_key":
                return str(existing_conn.get("device_key", existing_conn.get("password", "")) or "")
            return str(existing_conn.get(name, "") or "")

        def create_connection_control(field_def: dict[str, Any]) -> ft.TextField:
            name = str(field_def.get("name", "")).strip()
            label = str(field_def.get("label") or CONNECTION_FIELD_LABELS.get(name, name))
            required = bool(field_def.get("required"))
            kind = str(field_def.get("kind", "text")).lower()
            secret = bool(field_def.get("secret")) or kind == "password" or name in {"password", "device_key", "token"}
            multiline = kind in {"textarea", "multiline"} or name in {"headers", "body_template", "payload_template"}
            kwargs = {
                "label": f"{label} *" if required else label,
                "value": existing_connection_value(name),
                "hint_text": str(field_def.get("placeholder") or ""),
                "password": secret,
                "can_reveal_password": secret,
                "multiline": multiline,
            }
            if multiline:
                kwargs["min_lines"] = 3
            control = field(**kwargs)

            def validate_connection_field(value: Any, field=field_def, field_name=name):
                clean_value = validators.clean(value)
                validators.validate_connection_values({field_name: clean_value} if clean_value else {}, {field_name: field})
                return clean_value

            if name == "port":
                bind_digits_only(control, validate_connection_field)
            else:
                bind_live_validator(control, validate_connection_field)
            return control

        def apply_form_schema(preferred_provider: Any | None = None, source: str = "apply"):
            nonlocal active_schema_names, active_schema_defs
            provider_before = provider_dd.value
            current_type = device_type_code(type_dd.value)
            provider, allowed, fallback_used = sync_provider_options(current_type, preferred_provider, source)
            current_provider = resolve_provider_code(provider.get("code", provider.get("key", provider_dd.value)))
            schema_fields = provider_form_fields(provider)
            active_schema_names = {str(item.get("name", "")).strip() for item in schema_fields if isinstance(item, dict) and str(item.get("name", "")).strip()}
            active_schema_defs = {str(item.get("name", "")).strip(): item for item in schema_fields if isinstance(item, dict) and str(item.get("name", "")).strip()}

            connection_controls.clear()
            new_connection_controls: list[ft.Control] = []
            for field_def in schema_fields:
                name = str(field_def.get("name", "")).strip()
                if not name:
                    continue
                control = create_connection_control(field_def)
                connection_controls[name] = control
                new_connection_controls.append(control)

            connection_fields_column.controls.clear()
            connection_fields_column.controls.extend(new_connection_controls)
            connection_fields_column.visible = bool(connection_fields_column.controls)
            caps = device_type_capabilities(current_type)
            is_on_sw.visible = bool(caps.get("canToggle", True))
            if not is_on_sw.visible:
                is_on_sw.value = False
            protocol_tf.value = str(provider.get("protocol", "manual"))
            channel_tf.value = str(provider.get("channel", "local"))
            note_text.value = str(provider.get("note", ""))

            status_parts: list[str] = []
            if not catalog_is_loaded:
                status_parts.append("\u041a\u0430\u0442\u0430\u043b\u043e\u0433 \u0442\u0438\u043f\u043e\u0432 \u0438 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u043e\u0432 \u043d\u0435 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d. \u0414\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u0442\u043e\u043b\u044c\u043a\u043e \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u044b\u0439 \u0442\u0435\u0441\u0442\u043e\u0432\u044b\u0439 \u0440\u0435\u0436\u0438\u043c.")
            if fallback_used:
                status_parts.append(f"\u0412\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0439 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u0434\u043b\u044f \u0442\u0438\u043f\u0430 {current_type}; \u0432\u044b\u0431\u0440\u0430\u043d {provider_dd.value}.")
            if not provider:
                status_parts.append("\u0412\u044b\u0431\u0440\u0430\u043d\u043d\u044b\u0439 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0432 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0435.")
            if not schema_fields and current_provider != "mock":
                status_parts.append("\u0421\u0445\u0435\u043c\u0430 \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u0430 \u043f\u0443\u0441\u0442\u0430: \u043f\u043e\u043b\u044f \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b.")
            form_status_text.value = " ".join(status_parts)
            form_status_text.visible = bool(status_parts)

            debug_device_form(
                "apply_form_schema",
                source=source,
                type=current_type,
                preferred_provider=preferred_provider,
                provider_before=provider_before,
                provider_after=provider_dd.value,
                selected_provider=current_provider,
                allowed=allowed,
                protocol=protocol_tf.value,
                channel=channel_tf.value,
                fields=list(connection_controls.keys()),
                fallback_used=fallback_used,
            )

        def collect_connection() -> dict[str, str]:
            connection = {}
            for key, control in connection_controls.items():
                if active_schema_names and key not in active_schema_names:
                    continue
                clean = (control.value or "").strip()
                if clean:
                    connection[key] = clean
            return connection

        def ensure_connection_controls_valid():
            first_error = None
            for name, control in connection_controls.items():
                field_def = active_schema_defs.get(name, {"name": name, "label": CONNECTION_FIELD_LABELS.get(name, name)})

                def check(value: Any, field=field_def, field_name=name):
                    clean_value = validators.clean(value)
                    validators.validate_connection_values({field_name: clean_value} if clean_value else {}, {field_name: field})

                if not validate_control(control, check) and first_error is None:
                    first_error = control.error_text
            if first_error:
                raise ValueError(first_error)

        def on_type_change(e):
            provider_before = provider_dd.value
            raw_value = event_value(e, type_dd.value)
            debug_device_form(
                "on_type_change:before",
                source="type_change",
                e_control_value=getattr(getattr(e, "control", None), "value", None),
                e_data=getattr(e, "data", None),
                type_before=type_dd.value,
                provider_before=provider_before,
            )
            type_dd.value = device_type_code(raw_value)
            apply_form_schema(source="type_change")
            debug_device_form(
                "on_type_change:after",
                source="type_change",
                type=type_dd.value,
                provider_before=provider_before,
                provider_after=provider_dd.value,
                protocol=protocol_tf.value,
                channel=channel_tf.value,
                note=note_text.value,
            )
            update_dynamic_form_controls()

        def on_provider_change(e):
            provider_before = provider_dd.value
            raw_value = event_value(e, provider_dd.value)
            selected_provider = resolve_provider_code(raw_value)
            debug_device_form(
                "on_provider_change:before",
                source="provider_change",
                type=type_dd.value,
                e_control_value=getattr(getattr(e, "control", None), "value", None),
                e_data=getattr(e, "data", None),
                provider_before=provider_before,
                raw_value=raw_value,
                selected_provider=selected_provider,
            )
            provider_dd.value = selected_provider
            apply_form_schema(preferred_provider=selected_provider, source="provider_change")
            debug_device_form(
                "on_provider_change:after",
                source="provider_change",
                type=type_dd.value,
                provider_before=provider_before,
                provider_after=provider_dd.value,
                protocol=protocol_tf.value,
                channel=channel_tf.value,
                note=note_text.value,
            )
            update_dynamic_form_controls()

        type_dd.on_change = on_type_change
        provider_dd.on_change = on_provider_change
        type_dd.on_select = on_type_change
        provider_dd.on_select = on_provider_change
        apply_form_schema(preferred_provider=provider_key, source="init")

        async def test_connection():
            try:
                ensure_connection_controls_valid()
                validate_connection_values(collect_connection(), active_schema_defs)
                result = await api_request(
                    "post",
                    "/api/devices/validate-connection",
                    {
                        "provider": resolve_provider_code(provider_dd.value),
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

        async def save():
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "roomId": int(room_dd.value) if room_dd.value else None,
                    "room": (new_room_tf.value or "").strip() or None,
                    "isOn": bool(is_on_sw.value),
                    "type": device_type_code(type_dd.value),
                    "provider": resolve_provider_code(provider_dd.value),
                    "protocol": (protocol_tf.value or "manual").strip(),
                    "channel": (channel_tf.value or "local").strip(),
                    "externalId": (external_id_tf.value or "").strip(),
                    "manufacturer": (manufacturer_tf.value or "").strip(),
                    "model": (model_tf.value or "").strip(),
                    "connection": collect_connection(),
                }
                ensure_controls_valid(
                    [
                        (name_tf, lambda value: validators.require_safe_text(value, "Название", 2, 80)),
                        (external_id_tf, validators.require_identifier),
                        (manufacturer_tf, lambda value: validators.optional_safe_text(value, "Производитель", 2, 50)),
                        (model_tf, lambda value: validators.optional_safe_text(value, "Модель", 1, 80)),
                        (channel_tf, lambda value: validators.optional_code(value, "Канал", 50)),
                        (new_room_tf, lambda value: validators.optional_safe_text(value, "Новая комната", 2, 50, no_only_digits=True)),
                    ]
                )
                validators.require_safe_text(payload["name"], "Название", 2, 80)
                require_external_id(payload["externalId"])
                validators.optional_safe_text(payload["manufacturer"], "Производитель", 2, 50)
                validators.optional_safe_text(payload["model"], "Модель", 1, 80)
                require_selected(payload["type"], "Тип устройства", set(device_types()))
                require_selected(payload["provider"], "Провайдер", {provider_code(item.get("code", item.get("key", ""))) for item in providers_for_type(payload["type"])})
                require_selected(payload["protocol"], "Протокол")
                validators.optional_code(payload["channel"], "Канал", 50)
                if payload["roomId"] and payload["room"]:
                    raise ValueError("Комната: выбери комнату из списка или укажи новую, но не оба варианта сразу")
                if not payload["roomId"] and not payload["room"]:
                    raise ValueError("Комната: выбери комнату из списка или укажи новую")
                validators.optional_safe_text(payload["room"], "Новая комната", 2, 50, no_only_digits=True)
                ensure_connection_controls_valid()
                validate_connection_values(payload["connection"], active_schema_defs)
                if DEBUG_DEVICE_FORM:
                    print(
                        f"[device-save] type={payload['type']!r} provider={payload['provider']!r} connection_keys={sorted(payload['connection'].keys())!r}",
                        flush=True,
                    )
                if editing:
                    created = await api_request("put", f"/api/devices/{device['id']}", payload)
                    message = "Устройство обновлено"
                else:
                    created = await api_request("post", "/api/devices", payload)
                    message = "Устройство добавлено"
                close_dialog(dialog)
                await refresh_and_build("devices", "rooms", "logs")
                status = created.get("connectionStatus") if isinstance(created, dict) else None
                status_message = created.get("connectionMessage") if isinstance(created, dict) else ""
                show_message(f"{message}. Статус: {status or 'unknown'} {status_message or ''}".strip())
            except Exception as ex:
                print("[device-save:error]", repr(ex), flush=True)
                form_status_text.value = str(ex)
                form_status_text.visible = True
                test_result.value = str(ex)
                try:
                    dialog.update()
                except Exception:
                    page.update()
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
                        form_status_text,
                        connection_fields_column,
                        test_result,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Тест связи", on_click=async_click(lambda e: run_button_action(e, test_connection))),
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Сохранить", on_click=async_click(lambda e: run_button_action(e, save))),
            ],
        )
        show_dialog(dialog)

    async def move_device(device_id: int, room_id_value: str | None):
        if not room_id_value:
            show_message("Выбери комнату")
            return
        try:
            await api_request("put", f"/api/devices/{device_id}/room", {"roomId": int(room_id_value)})
            await refresh_and_build("devices", "rooms", "logs")
            show_message("Привязка устройства обновлена")
        except Exception as ex:
            show_message(str(ex))

    async def toggle_device(device_id: int):
        try:
            await api_request("put", f"/api/devices/{device_id}/toggle")
            await refresh_and_build("devices", "logs")
        except Exception as ex:
            show_message(str(ex))

    def delete_device(device_id: int, device_name: str):
        async def action():
            try:
                await api_request("delete", f"/api/devices/{device_id}")
                await refresh_and_build("devices", "rooms", "logs")
                show_message(f"Устройство удалено: {device_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить устройство", f"Удалить устройство «{device_name}»?", action)

    def open_room_dialog(room: dict[str, Any] | None = None):
        editing = room is not None
        name_tf = field(label="Название комнаты", value=(room or {}).get("name", ""))
        zone_tf = field(label="Зона", value=(room or {}).get("zone", ""), hint_text="Например: Первый этаж")
        bind_live_validator(name_tf, lambda value: validators.require_safe_text(value, "Название комнаты", 2, 50, no_only_digits=True))
        bind_live_validator(zone_tf, lambda value: validators.optional_free_text(value, "Зона", 500))

        async def save():
            try:
                payload = {"name": (name_tf.value or "").strip(), "zone": (zone_tf.value or "").strip()}
                ensure_controls_valid(
                    [
                        (name_tf, lambda value: validators.require_safe_text(value, "Название комнаты", 2, 50, no_only_digits=True)),
                        (zone_tf, lambda value: validators.optional_free_text(value, "Зона", 500)),
                    ]
                )
                if editing:
                    await api_request("put", f"/api/rooms/{room['id']}", payload)
                    message = "Комната обновлена"
                else:
                    await api_request("post", "/api/rooms", payload)
                    message = "Комната создана"
                close_dialog(dialog)
                await refresh_and_build("rooms", "devices", "logs")
                show_message(message)
            except Exception as ex:
                show_message(str(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Изменить комнату" if editing else "Создать комнату", weight=ft.FontWeight.BOLD),
            content=ft.Column(tight=True, spacing=10, controls=[name_tf, zone_tf]),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Сохранить", on_click=async_click(lambda e: run_button_action(e, save))),
            ],
        )
        show_dialog(dialog)

    def delete_room(room_id: int, room_name: str):
        async def action():
            try:
                await api_request("delete", f"/api/rooms/{room_id}")
                await refresh_and_build("rooms", "devices", "logs")
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
        bind_live_validator(name_tf, lambda value: validators.require_safe_text(value, "Название сценария", 3, 80))
        bind_live_validator(description_tf, lambda value: validators.optional_free_text(value, "Описание сценария", 500))

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

        async def save():
            actions = []
            order = 1
            for item_device, dd in device_controls:
                if dd.value == "skip":
                    continue
                actions.append({"deviceId": int(item_device.get("id", 0)), "targetIsOn": dd.value == "on", "sortOrder": order})
                order += 1
            try:
                payload = {"name": (name_tf.value or "").strip(), "description": (description_tf.value or "").strip(), "actions": actions}
                ensure_controls_valid(
                    [
                        (name_tf, lambda value: validators.require_safe_text(value, "Название сценария", 3, 80)),
                        (description_tf, lambda value: validators.optional_free_text(value, "Описание сценария", 500)),
                    ]
                )
                if not actions:
                    raise ValueError("Сценарий: добавьте хотя бы одно действие")
                for action in actions:
                    target_device = find_device_by_id(action["deviceId"])
                    if target_device is None:
                        raise ValueError("Сценарий: устройство не найдено")
                    if not device_can_receive_commands(target_device):
                        raise ValueError("Сценарий: датчик или камера не могут быть целевым устройством включения/выключения")
                if editing:
                    await api_request("put", f"/api/scenes/{scene['id']}", payload)
                    message = "Сценарий обновлен"
                else:
                    await api_request("post", "/api/scenes", payload)
                    message = "Сценарий создан"
                close_dialog(dialog)
                await refresh_and_build("scenes", "logs")
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
                ft.ElevatedButton("Сохранить", on_click=async_click(lambda e: run_button_action(e, save))),
            ],
        )
        show_dialog(dialog)

    async def run_scene(scene_id: int, scene_name: str):
        try:
            await api_request("post", f"/api/scenes/{scene_id}/run")
            await refresh_and_build("devices", "scenes", "logs")
            show_message(f"Сценарий запущен: {scene_name}")
        except Exception as ex:
            show_message(str(ex))

    def delete_scene(scene_id: int, scene_name: str):
        async def action():
            try:
                await api_request("delete", f"/api/scenes/{scene_id}")
                await refresh_and_build("scenes", "logs")
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
        bind_live_validator(name_tf, lambda value: validators.require_safe_text(value, "Название правила", 3, 80))
        bind_live_validator(description_tf, lambda value: validators.optional_free_text(value, "Описание правила", 500))
        bind_live_validator(event_type_tf, validators.validate_event_type)
        bind_live_validator(compare_tf, lambda value: validators.validate_event_value(event_type_tf.value, value, "Сравнить с"))

        async def save():
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
                ensure_controls_valid(
                    [
                        (name_tf, lambda value: validators.require_safe_text(value, "Название правила", 3, 80)),
                        (description_tf, lambda value: validators.optional_free_text(value, "Описание правила", 500)),
                        (event_type_tf, validators.validate_event_type),
                        (compare_tf, lambda value: validators.validate_event_value(event_type_tf.value, value, "Сравнить с")),
                    ]
                )
                if not payload["triggerDeviceId"]:
                    raise ValueError("Датчик / источник: нужно выбрать устройство")
                source_device = find_device_by_id(payload["triggerDeviceId"])
                if source_device is None:
                    raise ValueError("Датчик / источник: устройство не найдено")
                if not device_type_capabilities(source_device.get("type")).get("canEmitEvents", True):
                    raise ValueError("Датчик / источник: выбранное устройство не отправляет события")
                validators.validate_event_type(payload["eventType"])
                require_selected(payload["comparisonOperator"], "Оператор", set(rule_operators()))
                validators.validate_rule_operator(payload["eventType"], payload["comparisonOperator"])
                validators.validate_event_value(payload["eventType"], payload["compareValue"], "Сравнить с")
                require_selected(payload["actionKind"], "Тип действия", set(action_kinds()))
                if payload["actionKind"] == "device_state" and not payload["actionDeviceId"]:
                    raise ValueError("Целевое устройство: нужно выбрать устройство")
                if payload["actionKind"] == "device_state":
                    target_device = find_device_by_id(payload["actionDeviceId"])
                    if target_device is None:
                        raise ValueError("Целевое устройство: устройство не найдено")
                    if not device_can_receive_commands(target_device):
                        raise ValueError("Целевое устройство: датчик или камера не могут быть целью включения/выключения")
                if payload["actionKind"] == "scene_run" and not payload["actionSceneId"]:
                    raise ValueError("Сценарий: нужно выбрать сценарий")
                if editing:
                    await api_request("put", f"/api/rules/{rule['id']}", payload)
                    message = "Правило обновлено"
                else:
                    await api_request("post", "/api/rules", payload)
                    message = "Правило создано"
                close_dialog(dialog)
                await refresh_and_build("rules", "logs")
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
                ft.ElevatedButton("Сохранить", on_click=async_click(lambda e: run_button_action(e, save))),
            ],
        )
        show_dialog(dialog)

    def delete_rule(rule_id: int, rule_name: str):
        async def action():
            try:
                await api_request("delete", f"/api/rules/{rule_id}")
                await refresh_and_build("rules", "logs")
                show_message(f"Правило удалено: {rule_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить правило", f"Удалить правило «{rule_name}»?", action)

    async def set_rule_enabled(rule_id: int, is_enabled: bool):
        try:
            await api_request("put", f"/api/rules/{rule_id}/enabled", {"isEnabled": is_enabled})
            await refresh_and_build("rules", "logs")
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
        bind_live_validator(name_tf, lambda value: validators.require_safe_text(value, "Название расписания", 3, 80))
        bind_live_validator(description_tf, lambda value: validators.optional_free_text(value, "Описание расписания", 500))
        bind_live_validator(time_tf, validators.require_hhmm)

        selected_days = set((schedule or {}).get("daysOfWeek", [1, 2, 3, 4, 5]))
        day_boxes: list[tuple[int, ft.Checkbox]] = []
        for item in schedule_days():
            box = ft.Checkbox(label=str(item.get("title")), value=int(item.get("value")) in selected_days)
            day_boxes.append((int(item.get("value")), box))

        async def save():
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
                ensure_controls_valid(
                    [
                        (name_tf, lambda value: validators.require_safe_text(value, "Название расписания", 3, 80)),
                        (description_tf, lambda value: validators.optional_free_text(value, "Описание расписания", 500)),
                        (time_tf, validators.require_hhmm),
                    ]
                )
                require_hhmm(payload["timeOfDay"])
                if not payload["daysOfWeek"]:
                    raise ValueError("Дни недели: выберите хотя бы один день")
                require_selected(payload["actionKind"], "Тип действия", set(action_kinds()))
                if payload["actionKind"] == "device_state" and not payload["actionDeviceId"]:
                    raise ValueError("Целевое устройство: нужно выбрать устройство")
                if payload["actionKind"] == "device_state":
                    target_device = find_device_by_id(payload["actionDeviceId"])
                    if target_device is None:
                        raise ValueError("Целевое устройство: устройство не найдено")
                    if not device_can_receive_commands(target_device):
                        raise ValueError("Целевое устройство: датчик или камера не могут быть целью расписания")
                if payload["actionKind"] == "scene_run" and not payload["actionSceneId"]:
                    raise ValueError("Сценарий: нужно выбрать сценарий")
                if editing:
                    await api_request("put", f"/api/schedules/{schedule['id']}", payload)
                    message = "Расписание обновлено"
                else:
                    await api_request("post", "/api/schedules", payload)
                    message = "Расписание создано"
                close_dialog(dialog)
                await refresh_and_build("schedules", "logs")
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
                ft.ElevatedButton("Сохранить", on_click=async_click(lambda e: run_button_action(e, save))),
            ],
        )
        show_dialog(dialog)

    def delete_schedule(schedule_id: int, schedule_name: str):
        async def action():
            try:
                await api_request("delete", f"/api/schedules/{schedule_id}")
                await refresh_and_build("schedules", "logs")
                show_message(f"Расписание удалено: {schedule_name}")
            except Exception as ex:
                show_message(str(ex))

        confirm_action("Удалить расписание", f"Удалить расписание «{schedule_name}»?", action)

    async def set_schedule_enabled(schedule_id: int, is_enabled: bool):
        try:
            await api_request("put", f"/api/schedules/{schedule_id}/enabled", {"isEnabled": is_enabled})
            await refresh_and_build("schedules", "logs")
            show_message("Состояние расписания обновлено")
        except Exception as ex:
            show_message(str(ex))

    async def run_due_schedules():
        try:
            result = await api_request("post", "/api/schedules/run-due") or {}
            await refresh_and_build("devices", "schedules", "scenes", "logs")
            show_message(str(result.get("message", "Проверка расписаний выполнена")))
        except Exception as ex:
            show_message(str(ex))

    def open_event_dialog():
        source_device_dd = dropdown(label="Источник события", options=device_options(sensor_first=True))
        event_type_tf = field(label="Тип события", value="motion")
        value_tf = field(label="Значение", value="true")
        message_tf = field(label="Сообщение", value="Тестовое событие")
        bind_live_validator(event_type_tf, validators.validate_event_type)
        bind_live_validator(value_tf, lambda value: validators.validate_event_value(event_type_tf.value, value, "Значение"))
        bind_live_validator(message_tf, lambda value: validators.optional_free_text(value, "Сообщение", 1000))

        async def send_event():
            try:
                payload = {
                    "deviceId": int(source_device_dd.value or 0),
                    "eventType": (event_type_tf.value or "").strip(),
                    "value": (value_tf.value or "").strip(),
                    "message": (message_tf.value or "").strip(),
                }
                if not payload["deviceId"]:
                    raise ValueError("Источник события: нужно выбрать устройство")
                source_device = find_device_by_id(payload["deviceId"])
                if source_device is None:
                    raise ValueError("Источник события: устройство не найдено")
                if not device_type_capabilities(source_device.get("type")).get("canEmitEvents", True):
                    raise ValueError("Источник события: выбранное устройство не отправляет события")
                ensure_controls_valid(
                    [
                        (event_type_tf, validators.validate_event_type),
                        (value_tf, lambda value: validators.validate_event_value(event_type_tf.value, value, "Значение")),
                        (message_tf, lambda value: validators.optional_free_text(value, "Сообщение", 1000)),
                    ]
                )
                result = await api_request(
                    "post",
                    "/api/events",
                    payload,
                ) or {}
                close_dialog(dialog)
                await refresh_and_build("devices", "rules", "logs")
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
                ft.ElevatedButton("Отправить", on_click=async_click(lambda e: run_button_action(e, send_event))),
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
                    gradient=ft.LinearGradient(colors=["#1ab869", "#269ba6"]),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            T("CALHouse", size=26, weight=ft.FontWeight.BOLD, color="#ffffff"),
                            ft.Text(
                                "Привет)))))",
                                color="#e0e7ff",
                            ),
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.ElevatedButton("Добавить устройство", icon=ft.Icons.ADD, on_click=async_click(lambda e: run_button_action(e, lambda: open_device_dialog()))),
                                    ft.OutlinedButton(
                                        "Отправить событие",
                                        icon=ft.Icons.SENSORS,
                                        style=ft.ButtonStyle(color="#ffffff"),
                                        on_click=lambda e: open_event_dialog(),
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
            action_buttons = []
            if device_type_capabilities(device.get("type")).get("canToggle", True):
                action_buttons.append(ft.ElevatedButton("Toggle", icon=ft.Icons.POWER_SETTINGS_NEW, on_click=async_click(lambda e, device_id=device["id"]: run_button_action(e, lambda: toggle_device(device_id)))))
            action_buttons.extend([
                ft.OutlinedButton("Изменить", icon=ft.Icons.EDIT_OUTLINED, on_click=async_click(lambda e, d=device: run_button_action(e, lambda: open_device_dialog(d)))),
                ft.OutlinedButton("Удалить", icon=ft.Icons.DELETE_OUTLINE, on_click=lambda e, d=device: delete_device(int(d["id"]), str(d.get("name", "Устройство")))),
            ])
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
                                    TM(f"Тип: {device_type_title(device.get('type'))} · {provider_title(device.get('provider'))}", size=12),
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
                        controls=action_buttons,
                    ),
                    ft.Row(
                        spacing=10,
                        controls=[
                            room_dd,
                            ft.OutlinedButton("Переместить", icon=ft.Icons.SWAP_HORIZ, on_click=async_click(lambda e, device_id=device["id"], dd=room_dd: run_button_action(e, lambda: move_device(int(device_id), dd.value)))),
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
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Добавить", icon=ft.Icons.ADD, on_click=async_click(lambda e: run_button_action(e, lambda: open_device_dialog()))), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build(show_toast=True))))]),
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
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать комнату", icon=ft.Icons.ADD, on_click=lambda e: open_room_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("rooms", "devices", show_toast=True))))]),
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
                            ft.ElevatedButton("Запустить", icon=ft.Icons.PLAY_ARROW, on_click=async_click(lambda e, s=scene: run_button_action(e, lambda: run_scene(int(s["id"]), str(s.get("name", "Сценарий")))))),
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
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать сценарий", icon=ft.Icons.AUTO_AWESOME, on_click=lambda e: open_scene_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("scenes", show_toast=True))))]),
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
                    ft.Row(spacing=10, controls=[ft.ElevatedButton("Включить" if not rule.get("isEnabled") else "Выключить", icon=ft.Icons.TOGGLE_ON if rule.get("isEnabled") else ft.Icons.TOGGLE_OFF, on_click=async_click(lambda e, rid=rule["id"], enabled=not bool(rule.get("isEnabled")): run_button_action(e, lambda: set_rule_enabled(int(rid), enabled)))), ft.OutlinedButton("Тест событием", icon=ft.Icons.SENSORS, on_click=lambda e: open_event_dialog())]),
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
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать правило", icon=ft.Icons.ADD, on_click=lambda e: open_rule_dialog()), ft.OutlinedButton("Отправить событие", icon=ft.Icons.SENSORS, on_click=lambda e: open_event_dialog()), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("rules", show_toast=True))))]),
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
                    ft.Row(spacing=10, controls=[ft.ElevatedButton("Включить" if not schedule.get("isEnabled") else "Выключить", icon=ft.Icons.TOGGLE_ON if schedule.get("isEnabled") else ft.Icons.TOGGLE_OFF, on_click=async_click(lambda e, sid=schedule["id"], enabled=not bool(schedule.get("isEnabled")): run_button_action(e, lambda: set_schedule_enabled(int(sid), enabled)))), ft.OutlinedButton("Проверить сейчас", icon=ft.Icons.SCHEDULE, on_click=async_click(lambda e: run_button_action(e, run_due_schedules)))]),
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
                        ft.Row(spacing=10, controls=[ft.ElevatedButton("Создать расписание", icon=ft.Icons.ADD, on_click=lambda e: open_schedule_dialog()), ft.OutlinedButton("Проверить сейчас", icon=ft.Icons.SCHEDULE, on_click=async_click(lambda e: run_button_action(e, run_due_schedules))), ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("schedules", show_toast=True))))]),
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
                        ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("logs", show_toast=True)))),
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
                card(T("---", weight=ft.FontWeight.BOLD), TM(f"Base URL: {API_BASE}")),
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
        page.appbar = ft.AppBar(bgcolor=c("nav"), title=ft.Text("CALHouse", color=c("text"), weight=ft.FontWeight.BOLD), actions=[ft.IconButton(ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build(show_toast=True))), icon_color=c("text"))])
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

    await refresh_all()
    build()


ft.run(main)
