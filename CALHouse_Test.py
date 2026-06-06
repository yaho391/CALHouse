# -*- coding: utf-8 -*-
import flet as ft
import asyncio
import httpx
import json
from datetime import datetime
from time import perf_counter
from typing import Any
import validation as validators

API_BASE = "http://localhost:5000"
API_TIMEOUT_SECONDS = 3.0
DEBUG_DEVICE_FORM = False
HISTORY_LOG_LIMIT = 30
INITIAL_LIST_LIMIT = 25
LIST_PAGE_SIZE = 25
REFRESH_DEBOUNCE_SECONDS = 0.35
TAB_FADE_MS = 180
CARD_REVEAL_MS = 170
VISUAL_API_LOG_LIMIT = 8
VISUAL_SCENE_LOG_LIMIT = 8
VISUAL_AUTOMATION_LOG_LIMIT = 8
DEMO_CLOCK_START_MINUTES = 8 * 60
DEMO_CLOCK_TICK_SECONDS = 2.0

LIGHT_BG = "#E6F0FF"
DARK_BG = "#0D1B2A"
GRADIENT_LIGHT = "#EAF7F2"
GRADIENT_LIGHT_END = "#CFE3FF"
GRADIENT_DARK = "#1E3A5F"
ACCENT = "#2DD4BF"
ACCENT_HOVER = "#14B8A6"
LIGHT_CARD = "#FFFFFF"
LIGHT_CARD_ALT = "#F8FAFC"
LIGHT_TEXT = "#425885"
LIGHT_MUTED_TEXT = "#6B7EA6"
DARK_CARD = "#111827"
DARK_CARD_ALT = "#1F2937"
DARK_TEXT = "#2AA6B8"
DARK_MUTED_TEXT = "#1E7F93"
BORDER_LIGHT = "#D8E3F0"
BORDER_DARK = "#243244"

LIGHT_PALETTE = {
    "bg": LIGHT_BG,
    "card": LIGHT_CARD,
    "border": BORDER_LIGHT,
    "text": LIGHT_TEXT,
    "muted": LIGHT_MUTED_TEXT,
    "field": LIGHT_CARD_ALT,
    "nav": LIGHT_CARD,
    "nav_indicator": GRADIENT_LIGHT,
    "accent": ACCENT,
    "accent_hover": ACCENT_HOVER,
    "gradient_start": GRADIENT_LIGHT,
    "gradient_end": GRADIENT_LIGHT_END,
    "hero_bg": GRADIENT_LIGHT_END,
    "hero_text": LIGHT_TEXT,
    "hero_muted": LIGHT_MUTED_TEXT,
    "warning_text": "#92400E",
    "snackbar_bg": GRADIENT_DARK,
    "snackbar_text": DARK_TEXT,
}

DARK_PALETTE = {
    "bg": DARK_BG,
    "card": DARK_CARD,
    "border": BORDER_DARK,
    "text": DARK_TEXT,
    "muted": DARK_MUTED_TEXT,
    "field": DARK_CARD_ALT,
    "nav": DARK_CARD,
    "nav_indicator": BORDER_DARK,
    "accent": ACCENT,
    "accent_hover": ACCENT_HOVER,
    "gradient_start": GRADIENT_DARK,
    "gradient_end": DARK_BG,
    "hero_bg": GRADIENT_DARK,
    "hero_text": DARK_TEXT,
    "hero_muted": DARK_MUTED_TEXT,
    "warning_text": "#FBBF24",
    "snackbar_bg": DARK_CARD,
    "snackbar_text": DARK_TEXT,
}

STATUS_COLORS = {
    "connected": ("#DCFCE7", "#166534"),
    "completed": ("#DCFCE7", "#166534"),
    "enabled": ("#DBEAFE", "#1D4ED8"),
    "no_connection": ("#FEE2E2", "#991B1B"),
    "pending": ("#FEF3C7", "#92400E"),
    "warning": ("#FEF3C7", "#92400E"),
    "disabled": ("#E2E8F0", "#475569"),
    "unknown": ("#E2E8F0", "#475569"),
}

DEMO_DEVICE_TYPES = {
    "demo_light": {
        "title": "Лампа",
        "device_type": "light",
        "category": "toggle",
        "icon": ft.Icons.LIGHTBULB_OUTLINE,
        "icon_on": ft.Icons.LIGHTBULB,
        "status_on": "включена",
        "status_off": "выключена",
        "model": "Demo Light",
    },
    "demo_socket": {
        "title": "Розетка",
        "device_type": "socket",
        "category": "toggle",
        "icon": ft.Icons.OUTLET,
        "icon_on": ft.Icons.ELECTRICAL_SERVICES,
        "status_on": "включена",
        "status_off": "выключена",
        "model": "Demo Socket",
    },
    "demo_motion_sensor": {
        "title": "Датчик движения",
        "device_type": "motion_sensor",
        "category": "motion",
        "icon": ft.Icons.SENSORS_OUTLINED,
        "icon_on": ft.Icons.SENSORS,
        "status_on": "Движение обнаружено",
        "status_off": "Движения нет",
        "model": "Demo Motion Sensor",
    },
    "demo_temperature_sensor": {
        "title": "Датчик температуры",
        "device_type": "temperature_sensor",
        "category": "temperature",
        "icon": ft.Icons.DEVICE_THERMOSTAT,
        "model": "Demo Temperature Sensor",
        "default_temperature": 24,
    },
    "demo_leak_sensor": {
        "title": "Датчик протечки",
        "device_type": "leak_sensor",
        "category": "leak",
        "icon": ft.Icons.WATER_DROP,
        "icon_on": ft.Icons.WATER_DAMAGE,
        "status_on": "Обнаружена протечка",
        "status_off": "Протечки нет",
        "model": "Demo Leak Sensor",
    },
}

VISUAL_RULES = [
    {"id": "motion_light", "name": "Движение включает свет", "trigger": "motion=true", "action": "demo_light ON"},
    {"id": "leak_socket_off", "name": "Протечка выключает розетку", "trigger": "leak=true", "action": "demo_socket OFF"},
    {"id": "temperature_socket_on", "name": "Высокая температура включает розетку", "trigger": "temperature > 28", "action": "demo_socket ON"},
    {"id": "evening_light", "name": "Вечером включить свет", "trigger": "demo-time evening", "action": "demo_light ON"},
    {"id": "night_socket_off", "name": "Ночью выключить розетку", "trigger": "demo-time night", "action": "demo_socket OFF"},
]

VISUAL_SCENARIOS = [
    {"id": "evening_mode", "name": "Вечерний режим", "icon": ft.Icons.LIGHT_MODE},
    {"id": "night_mode", "name": "Ночной режим", "icon": ft.Icons.NIGHTLIGHT},
    {"id": "safety", "name": "Безопасность", "icon": ft.Icons.SECURITY},
    {"id": "all_off", "name": "Все выключить", "icon": ft.Icons.POWER_SETTINGS_NEW},
]

DEFAULT_DEVICE_TYPES = [
    {"code": "light", "displayName": "Свет", "capabilities": {"canToggle": True}, "allowedProviders": ["mock"]},
    {"code": "socket", "displayName": "Розетка", "capabilities": {"canToggle": True}, "allowedProviders": ["mock"]},
    {"code": "relay", "displayName": "Реле", "capabilities": {"canToggle": True}, "allowedProviders": ["mock"]},
    {"code": "motion_sensor", "displayName": "Датчик движения", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
    {"code": "temperature_sensor", "displayName": "Датчик температуры", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
    {"code": "leak_sensor", "displayName": "Датчик протечки", "capabilities": {"canToggle": False}, "allowedProviders": ["mock"]},
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
EVENT_TYPE_CODES = [
    "motion",
    "temperature",
    "humidity",
    "smoke",
    "water_leak",
    "door_open",
    "battery",
    "power",
    "online",
    "offline",
    "button_click",
    "state",
]
EVENT_TYPE_LABELS = {
    "motion": "motion - движение",
    "temperature": "temperature - температура",
    "humidity": "humidity - влажность",
    "smoke": "smoke - дым",
    "water_leak": "water_leak - протечка",
    "door_open": "door_open - дверь",
    "battery": "battery - батарея",
    "power": "power - питание",
    "online": "online - онлайн",
    "offline": "offline - офлайн",
    "button_click": "button_click - кнопка",
    "state": "state - состояние",
}
EVENT_TYPES_BY_DEVICE_TYPE = {
    "motion_sensor": {"motion", "battery", "online", "offline"},
    "temperature_sensor": {"temperature", "humidity", "battery", "online", "offline"},
    "leak_sensor": {"water_leak", "battery", "online", "offline"},
}
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

    state = {
        "tab": 0,
        "dark": False,
        "token": None,
        "login": "",
        "role": "",
        "auth_refresh_task": None,
        "loading_sections": set(),
        "refreshing_keys": set(),
        "last_refresh_started": {},
        "visible_limits": {"devices": INITIAL_LIST_LIMIT, "rules": INITIAL_LIST_LIMIT, "logs": INITIAL_LIST_LIMIT},
        "pending_card_reveals": [],
        "visual_room_id": None,
        "visual_api_logs": [],
        "visual_pending_devices": set(),
        "visual_sensor_values": {},
        "visual_scene_logs": [],
        "visual_automation_logs": [],
        "visual_pending_automation": set(),
        "visual_demo_time_minutes": DEMO_CLOCK_START_MINUTES,
        "visual_demo_time_running": False,
        "visual_demo_clock_task": None,
        "visual_day_phase": "day",
        "visual_clock_controls": {},
        "visual_scene_controls": {},
    }
    api_client = httpx.AsyncClient(base_url=API_BASE, timeout=API_TIMEOUT_SECONDS)

    def close_api_client(_=None):
        clock_task = state.get("visual_demo_clock_task")
        if isinstance(clock_task, asyncio.Task) and not clock_task.done():
            clock_task.cancel()
        state["visual_demo_time_running"] = False
        if not api_client.is_closed:
            asyncio.create_task(api_client.aclose())

    page.on_close = close_api_client
    page.on_disconnect = close_api_client
    data: dict[str, Any] = {
        "catalog": {},
        "devices": [],
        "rooms": [],
        "scenes": [],
        "rules": [],
        "schedules": [],
        "logs": [],
        "users": [],
    }

    content = ft.Container(
        expand=True,
        padding=20,
        opacity=1,
        animate=ft.Animation(160, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(TAB_FADE_MS, ft.AnimationCurve.EASE_OUT),
    )

    def palette() -> dict[str, str]:
        return DARK_PALETTE if state["dark"] else LIGHT_PALETTE

    def c(name: str) -> str:
        return palette()[name]

    def T(text: str, **kwargs):
        return ft.Text(text, color=kwargs.pop("color", c("text")), **kwargs)

    def TM(text: str, **kwargs):
        return ft.Text(text, color=kwargs.pop("color", c("muted")), **kwargs)

    def is_section_loading(*sections: str) -> bool:
        loading = state.get("loading_sections")
        return bool(isinstance(loading, set) and loading.intersection(sections))

    def loading_banner(*sections: str):
        if not is_section_loading(*sections):
            return None
        return ft.Container(
            padding=10,
            bgcolor=c("field"),
            border_radius=12,
            border=ft.border.all(1, c("border")),
            animate=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
            content=ft.Row(
                spacing=10,
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=c("accent")),
                    TM("Обновление данных...", size=12),
                ],
            ),
        )

    def visible_items(section: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        limits = state.get("visible_limits")
        limit = INITIAL_LIST_LIMIT
        if isinstance(limits, dict):
            limit = int(limits.get(section, INITIAL_LIST_LIMIT) or INITIAL_LIST_LIMIT)
        return items[:limit]

    def show_more_button(section: str, total: int):
        limits = state.get("visible_limits")
        current = INITIAL_LIST_LIMIT
        if isinstance(limits, dict):
            current = int(limits.get(section, INITIAL_LIST_LIMIT) or INITIAL_LIST_LIMIT)
        if total <= current:
            return None

        def show_more(_):
            if isinstance(state.get("visible_limits"), dict):
                state["visible_limits"][section] = current + LIST_PAGE_SIZE
            render_current_view()

        remaining = total - current
        return ft.OutlinedButton(f"Показать ещё ({remaining})", icon=ft.Icons.EXPAND_MORE, on_click=show_more)

    def clear_pending_card_reveals():
        pending = state.get("pending_card_reveals")
        if isinstance(pending, list):
            pending.clear()

    def prepare_card_reveal(item: ft.Container):
        item.opacity = 0
        item.offset = ft.Offset(0, 0.015)
        item.animate_opacity = ft.Animation(CARD_REVEAL_MS, ft.AnimationCurve.EASE_OUT)
        item.animate_offset = ft.Animation(CARD_REVEAL_MS, ft.AnimationCurve.EASE_OUT)
        pending = state.get("pending_card_reveals")
        if isinstance(pending, list):
            pending.append(item)
        return item

    def card(*controls: ft.Control, padding: int = 16, expand: bool = False):
        item = ft.Container(
            expand=expand,
            padding=padding,
            bgcolor=c("card"),
            border_radius=16,
            border=ft.border.all(1, c("border")),
            animate=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(spacing=10, controls=list(controls)),
        )
        return prepare_card_reveal(item)

    async def reveal_cards():
        pending = state.get("pending_card_reveals")
        if not isinstance(pending, list) or not pending:
            return
        cards = [item for item in pending if getattr(item, "page", None)]
        pending.clear()
        if not cards:
            return
        await asyncio.sleep(0.01)
        for item in cards:
            item.opacity = 1
            item.offset = ft.Offset(0, 0)
            try:
                item.update()
            except Exception:
                pass

    def schedule_card_reveal():
        pending = state.get("pending_card_reveals")
        if isinstance(pending, list) and pending:
            try:
                asyncio.create_task(reveal_cards())
            except RuntimeError:
                pending.clear()

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
        page.snack_bar = ft.SnackBar(
            bgcolor=c("snackbar_bg"),
            content=ft.Text(text, color=c("snackbar_text")),
        )
        page.snack_bar.open = True
        page.update()

    def invalid_input_message(detail: Any = None) -> str:
        prefix = "Данные введены неправильно"
        text = str(detail or "").strip()
        if not text:
            return prefix
        if text.startswith(prefix):
            return text
        return f"{prefix}: {text}"

    def error_message(ex: Exception) -> str:
        if isinstance(ex, ValueError):
            return invalid_input_message(ex)
        return str(ex)

    def api_error_message(path: str, status_code: int, error_data: dict[str, Any], fallback: str) -> str:
        code = str(error_data.get("code") or "").strip()
        auth_messages = {
            "AUTH_INVALID_CREDENTIALS": "Неправильно введен логин или пароль",
            "AUTH_USER_BLOCKED": "Пользователь заблокирован",
            "AUTH_LOGIN_EXISTS": "Такой логин уже существует",
            "AUTH_LOGIN_INVALID": "Логин заполнен неправильно",
            "AUTH_PASSWORD_INVALID": "Пароль заполнен неправильно",
            "AUTH_PASSWORD_CONFIRMATION_MISMATCH": "Пароли не совпадают",
        }
        if code in auth_messages:
            return auth_messages[code] if code == "AUTH_INVALID_CREDENTIALS" else invalid_input_message(auth_messages[code])
        if path == "/api/auth/login" and str(fallback or "").strip().lower() == "invalid login or password":
            return "Неправильно введен логин или пароль"
        if path.startswith("/api/auth/") and status_code == 400:
            return invalid_input_message(fallback)
        return fallback

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
        try:
            headers = {}
            if state.get("token"):
                headers["Authorization"] = f"Bearer {state['token']}"
            response = await api_client.request(method=method.upper(), url=path, json=payload, headers=headers, timeout=timeout)
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {}
                error_code = str(error_data.get("code") or "").strip()
                if not (path == "/api/auth/login" and error_code == "AUTH_INVALID_CREDENTIALS"):
                    print(f"[api:error] status_code={response.status_code}", flush=True)
                    print(f"[api:error] response.text={response.text}", flush=True)
                message = error_data.get("message") or error_data.get("error") or f"HTTP {response.status_code}"
                message = api_error_message(path, response.status_code, error_data, message)
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
                if response.status_code == 400 and not (
                    path == "/api/auth/login" and "логин или пароль" in message.lower()
                ):
                    message = invalid_input_message(message)
                raise RuntimeError(message)
            if not response.text:
                return None
            return response.json()
        except httpx.TimeoutException as ex:
            raise RuntimeError("Сервер долго не отвечает или устройство не ответило") from ex
        except httpx.RequestError as ex:
            raise RuntimeError(f"API недоступен: {ex}") from ex

    def visual_api_body_text(payload: dict[str, Any] | None) -> str:
        if payload is None:
            return ""
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def add_visual_api_log(entry: dict[str, Any]):
        logs = state.get("visual_api_logs")
        if not isinstance(logs, list):
            logs = []
            state["visual_api_logs"] = logs
        logs.insert(0, entry)
        del logs[VISUAL_API_LOG_LIMIT:]

    async def visualization_api_request(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = API_TIMEOUT_SECONDS):
        started_at = perf_counter()
        status: int | str = "error"
        error_text = ""
        try:
            headers = {}
            if state.get("token"):
                headers["Authorization"] = f"Bearer {state['token']}"
            response = await api_client.request(method=method.upper(), url=path, json=payload, headers=headers, timeout=timeout)
            status = response.status_code
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {}
                message = error_data.get("message") or error_data.get("error") or f"HTTP {response.status_code}"
                message = api_error_message(path, response.status_code, error_data, message)
                if response.status_code == 400:
                    message = invalid_input_message(message)
                error_text = message
                raise RuntimeError(message)
            if not response.text:
                return None
            return response.json()
        except httpx.TimeoutException as ex:
            status = "timeout"
            error_text = "Сервер долго не отвечает или устройство не ответило"
            raise RuntimeError(error_text) from ex
        except httpx.RequestError as ex:
            status = "error"
            error_text = f"API недоступен: {ex}"
            raise RuntimeError(error_text) from ex
        finally:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            add_visual_api_log(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "method": method.upper(),
                    "path": path,
                    "body": visual_api_body_text(payload),
                    "status": status,
                    "durationMs": elapsed_ms,
                    "error": error_text,
                }
            )

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

    def set_control_error(control: ft.Control, message: str | None):
        if hasattr(control, "error"):
            control.error = message
        elif hasattr(control, "error_text"):
            control.error_text = message

    def get_control_error(control: ft.Control) -> str | None:
        value = getattr(control, "error", None)
        if value:
            return str(value)
        value = getattr(control, "error_text", None)
        return str(value) if value else None

    def validate_control(control: ft.Control, validator) -> bool:
        try:
            validator(getattr(control, "value", None))
            set_control_error(control, None)
            ok = True
        except Exception as ex:
            set_control_error(control, error_message(ex))
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
                first_error = get_control_error(control)
        if first_error:
            raise ValueError(first_error)

    def is_authenticated() -> bool:
        return bool(state.get("token"))

    def is_admin() -> bool:
        return str(state.get("role", "")).lower() == "admin"

    def clear_data():
        data["catalog"] = {}
        data["devices"] = []
        data["rooms"] = []
        data["scenes"] = []
        data["rules"] = []
        data["schedules"] = []
        data["logs"] = []
        data["users"] = []

    async def load_catalog(show_error: bool = False):
        try:
            data["catalog"] = await api_request("get", "/api/device-catalog") or {}
        except Exception as ex:
            data["catalog"] = {}
            if show_error:
                show_message(error_message(ex))

    async def load_devices(show_error: bool = False):
        try:
            items = await api_request("get", "/api/devices") or []
            data["devices"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(error_message(ex))

    async def load_rooms(show_error: bool = False):
        try:
            items = await api_request("get", "/api/rooms") or []
            data["rooms"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(error_message(ex))

    async def load_scenes(show_error: bool = False):
        try:
            items = await api_request("get", "/api/scenes") or []
            data["scenes"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(error_message(ex))

    async def load_rules(show_error: bool = False):
        try:
            items = await api_request("get", "/api/rules") or []
            data["rules"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(error_message(ex))

    async def load_schedules(show_error: bool = False):
        try:
            items = await api_request("get", "/api/schedules") or []
            data["schedules"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(error_message(ex))

    async def load_logs(show_error: bool = False):
        try:
            items = await api_request("get", f"/api/logs?limit={HISTORY_LOG_LIMIT}") or []
            data["logs"] = items if isinstance(items, list) else []
        except Exception as ex:
            if show_error:
                show_message(error_message(ex))

    async def load_users(show_error: bool = False):
        if not is_admin():
            data["users"] = []
            return
        try:
            items = await api_request("get", "/api/users") or []
            data["users"] = items if isinstance(items, list) else []
        except Exception as ex:
            data["users"] = []
            if show_error:
                show_message(error_message(ex))

    async def refresh_all(show_toast: bool = False):
        if not is_authenticated():
            clear_data()
            return
        await asyncio.gather(
            load_catalog(show_error=True),
            load_rooms(show_error=True),
            load_devices(show_error=True),
            load_scenes(show_error=True),
            load_rules(show_error=True),
            load_schedules(show_error=True),
            load_logs(show_error=True),
            load_users(show_error=True),
        )
        if show_toast:
            show_message("Данные обновлены")

    async def refresh_sections(*sections: str, show_toast: bool = False):
        if not is_authenticated():
            clear_data()
            return
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
        if "users" in sections:
            tasks.append(load_users(show_error=True))
        if tasks:
            await asyncio.gather(*tasks)
        if show_toast:
            show_message("Данные обновлены")

    def current_tab_sections() -> tuple[str, ...]:
        sections_by_tab = {
            0: ("devices", "rooms", "scenes", "rules", "schedules", "logs"),
            1: ("devices", "rooms", "logs"),
            2: ("rooms", "devices", "logs"),
            3: ("scenes", "logs"),
            4: ("rules", "logs"),
            5: ("schedules", "logs"),
            6: ("rooms", "devices"),
            7: ("logs",),
            8: ("users",),
        }
        return sections_by_tab.get(int(state.get("tab", 0) or 0), ("devices", "rooms", "logs"))

    async def refresh_and_build(*sections: str, show_toast: bool = False):
        target_sections = sections or current_tab_sections()
        key = tuple(sorted(target_sections))
        loop_time = asyncio.get_running_loop().time()
        refreshing_keys = state.get("refreshing_keys")
        last_refresh_started = state.get("last_refresh_started")
        if not isinstance(refreshing_keys, set):
            refreshing_keys = set()
            state["refreshing_keys"] = refreshing_keys
        if not isinstance(last_refresh_started, dict):
            last_refresh_started = {}
            state["last_refresh_started"] = last_refresh_started
        if key in refreshing_keys:
            return
        if loop_time - float(last_refresh_started.get(key, 0) or 0) < REFRESH_DEBOUNCE_SECONDS:
            return

        refreshing_keys.add(key)
        last_refresh_started[key] = loop_time
        loading_sections = state.get("loading_sections")
        if not isinstance(loading_sections, set):
            loading_sections = set()
            state["loading_sections"] = loading_sections
        loading_sections.update(target_sections)
        render_current_view()
        try:
            await refresh_sections(*target_sections, show_toast=show_toast)
        finally:
            loading_sections.difference_update(target_sections)
            refreshing_keys.discard(key)
        render_current_view()

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
        if control is not None and old_disabled is True:
            return
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
            show_message(error_message(ex))
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
            sensor_types = {"motion_sensor", "temperature_sensor", "leak_sensor"}
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

    def event_type_options() -> list[ft.dropdown.Option]:
        allowed = validators.ALLOWED_EVENTS
        return [ft.dropdown.Option(code, EVENT_TYPE_LABELS.get(code, code)) for code in EVENT_TYPE_CODES if code in allowed]

    def allowed_events_for_device(device: dict[str, Any]) -> set[str]:
        if not device_type_capabilities(device.get("type")).get("canEmitEvents", True):
            return set()
        type_code = device_type_code(device.get("type"))
        return set(EVENT_TYPES_BY_DEVICE_TYPE.get(type_code, validators.ALLOWED_EVENTS))

    def validate_rule_event_compatibility(device_id: Any, event_type: Any) -> str:
        event = validators.validate_event_type(event_type)
        device = find_device_by_id(device_id)
        if device is None:
            raise ValueError("Датчик / источник: устройство не найдено")
        allowed = allowed_events_for_device(device)
        if not allowed:
            raise ValueError("Датчик / источник: выбранное устройство не отправляет события")
        if event not in allowed:
            available = ", ".join(code for code in EVENT_TYPE_CODES if code in allowed)
            raise ValueError(f"Событие {event} недоступно для выбранного устройства. Доступно: {available}")
        return event

    def schedule_days_title(days: list[int] | None) -> str:
        days = days or []
        lookup = {int(item["value"]): str(item["title"]) for item in schedule_days()}
        return ", ".join(lookup.get(day, str(day)) for day in days) or "—"

    def stat_card(title: str, value: str, icon: str, tab_index: int | None = None):
        item = ft.Container(
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
            on_click=async_click(lambda e: switch_tab(tab_index)) if tab_index is not None else None,
        )
        return prepare_card_reveal(item)

    async def switch_tab(index: int):
        state["tab"] = index
        await render_current_view_animated(update_nav=True)

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
        bg, fg = STATUS_COLORS.get(str(status or "unknown"), STATUS_COLORS["unknown"])
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
        form_status_text = TM("", size=12, color=c("warning_text"))
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
                    first_error = get_control_error(control)
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
                show_message(error_message(ex))

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
                show_message(error_message(ex))

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
            show_message(error_message(ex))

    async def toggle_device(device_id: int):
        try:
            await api_request("put", f"/api/devices/{device_id}/toggle")
            await refresh_and_build("devices", "logs")
        except Exception as ex:
            show_message(error_message(ex))

    def copy_container_state(target: ft.Container, source: ft.Container):
        target.bgcolor = source.bgcolor
        target.border_radius = source.border_radius
        target.padding = source.padding
        target.content = source.content

    def update_device_card_controls(device: dict[str, Any], status_control: ft.Container, power_control: ft.Container, message_control: ft.Text):
        copy_container_state(status_control, status_chip(str(device.get("connectionStatus", "unknown")), device.get("connectionStatus")))
        copy_container_state(power_control, bool_chip(bool(device.get("isOn"))))
        message_control.value = device.get("connectionMessage") or ""
        for control in (status_control, power_control, message_control):
            try:
                if getattr(control, "page", None):
                    control.update()
            except Exception:
                pass

    async def toggle_device_card(device_id: int, status_control: ft.Container, power_control: ft.Container, message_control: ft.Text):
        cached = find_device_by_id(device_id)
        old_snapshot = dict(cached) if cached else None
        if cached is not None:
            cached["isOn"] = not bool(cached.get("isOn"))
            cached["connectionStatus"] = "pending"
            cached["connectionMessage"] = "Команда отправлена..."
            update_device_card_controls(cached, status_control, power_control, message_control)
        try:
            result = await api_request("put", f"/api/devices/{device_id}/toggle")
            if cached is not None and isinstance(result, dict):
                cached.update(result)
                update_device_card_controls(cached, status_control, power_control, message_control)
        except Exception:
            if cached is not None and old_snapshot is not None:
                cached.clear()
                cached.update(old_snapshot)
                update_device_card_controls(cached, status_control, power_control, message_control)
            raise

    def delete_device(device_id: int, device_name: str):
        async def action():
            try:
                await api_request("delete", f"/api/devices/{device_id}")
                await refresh_and_build("devices", "rooms", "logs")
                show_message(f"Устройство удалено: {device_name}")
            except Exception as ex:
                show_message(error_message(ex))

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
                show_message(error_message(ex))

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
                show_message(error_message(ex))

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
                show_message(error_message(ex))

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
            show_message(error_message(ex))

    def delete_scene(scene_id: int, scene_name: str):
        async def action():
            try:
                await api_request("delete", f"/api/scenes/{scene_id}")
                await refresh_and_build("scenes", "logs")
                show_message(f"Сценарий удален: {scene_name}")
            except Exception as ex:
                show_message(error_message(ex))

        confirm_action("Удалить сценарий", f"Удалить сценарий «{scene_name}»?", action)

    def open_rule_dialog(rule: dict[str, Any] | None = None):
        editing = rule is not None
        name_tf = field(label="Название правила", value=(rule or {}).get("name", ""))
        description_tf = field(label="Описание", value=(rule or {}).get("description", ""), multiline=True, min_lines=2, max_lines=3)
        enabled_sw = ft.Switch(label="Правило активно", value=bool((rule or {}).get("isEnabled", True)))
        trigger_device_dd = dropdown(label="Датчик / источник", value=str(rule.get("triggerDeviceId")) if editing and rule.get("triggerDeviceId") is not None else None, options=device_options(sensor_first=True))
        event_type_dd = dropdown(label="Тип события", value=(rule or {}).get("triggerEventType", "motion"), options=event_type_options())
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
        rule_status_text = TM("", size=12, color=c("warning_text"))
        rule_status_text.visible = False
        bind_live_validator(name_tf, lambda value: validators.require_safe_text(value, "Название правила", 3, 80))
        bind_live_validator(description_tf, lambda value: validators.optional_free_text(value, "Описание правила", 500))
        bind_live_validator(compare_tf, lambda value: validators.validate_event_value(event_type_dd.value, value, "Сравнить с"))

        def update_rule_event_status():
            message = ""
            if trigger_device_dd.value and event_type_dd.value:
                try:
                    validate_rule_event_compatibility(trigger_device_dd.value, event_type_dd.value)
                    set_control_error(event_type_dd, None)
                except Exception as ex:
                    message = error_message(ex)
                    set_control_error(event_type_dd, message)
            else:
                set_control_error(event_type_dd, None)
            rule_status_text.value = message
            rule_status_text.visible = bool(message)
            for control in (event_type_dd, rule_status_text):
                try:
                    if getattr(control, "page", None):
                        control.update()
                except Exception:
                    pass

        def on_rule_event_change(_):
            validate_control(event_type_dd, validators.validate_event_type)
            validate_control(compare_tf, lambda value: validators.validate_event_value(event_type_dd.value, value, "Сравнить с"))
            update_rule_event_status()

        def on_rule_source_change(_):
            update_rule_event_status()

        event_type_dd.on_change = on_rule_event_change
        trigger_device_dd.on_change = on_rule_source_change
        update_rule_event_status()

        async def save():
            try:
                payload = {
                    "name": (name_tf.value or "").strip(),
                    "description": (description_tf.value or "").strip(),
                    "isEnabled": bool(enabled_sw.value),
                    "triggerDeviceId": int(trigger_device_dd.value or 0),
                    "eventType": (event_type_dd.value or "").strip(),
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
                        (event_type_dd, validators.validate_event_type),
                        (compare_tf, lambda value: validators.validate_event_value(event_type_dd.value, value, "Сравнить с")),
                    ]
                )
                if not payload["triggerDeviceId"]:
                    raise ValueError("Датчик / источник: нужно выбрать устройство")
                source_device = find_device_by_id(payload["triggerDeviceId"])
                if source_device is None:
                    raise ValueError("Датчик / источник: устройство не найдено")
                if not device_type_capabilities(source_device.get("type")).get("canEmitEvents", True):
                    raise ValueError("Датчик / источник: выбранное устройство не отправляет события")
                validate_rule_event_compatibility(payload["triggerDeviceId"], payload["eventType"])
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
                show_message(error_message(ex))

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
                        ft.Row(spacing=10, controls=[trigger_device_dd, event_type_dd]),
                        rule_status_text,
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
                show_message(error_message(ex))

        confirm_action("Удалить правило", f"Удалить правило «{rule_name}»?", action)

    async def set_rule_enabled(rule_id: int, is_enabled: bool):
        try:
            await api_request("put", f"/api/rules/{rule_id}/enabled", {"isEnabled": is_enabled})
            await refresh_and_build("rules", "logs")
            show_message("Состояние правила обновлено")
        except Exception as ex:
            show_message(error_message(ex))

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
                show_message(error_message(ex))

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
                show_message(error_message(ex))

        confirm_action("Удалить расписание", f"Удалить расписание «{schedule_name}»?", action)

    async def set_schedule_enabled(schedule_id: int, is_enabled: bool):
        try:
            await api_request("put", f"/api/schedules/{schedule_id}/enabled", {"isEnabled": is_enabled})
            await refresh_and_build("schedules", "logs")
            show_message("Состояние расписания обновлено")
        except Exception as ex:
            show_message(error_message(ex))

    async def run_due_schedules():
        try:
            result = await api_request("post", "/api/schedules/run-due") or {}
            await refresh_and_build("devices", "schedules", "scenes", "logs")
            show_message(str(result.get("message", "Проверка расписаний выполнена")))
        except Exception as ex:
            show_message(error_message(ex))

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
                show_message(error_message(ex))

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

    def visual_selected_room_id() -> str | None:
        rooms = data["rooms"]
        if not rooms:
            state["visual_room_id"] = None
            return None
        available = {str(room.get("id")) for room in rooms}
        selected = str(state.get("visual_room_id") or "")
        if selected not in available:
            selected = str(rooms[0].get("id"))
            state["visual_room_id"] = selected
        return selected

    def is_demo_device(device: dict[str, Any]) -> bool:
        connection = device.get("connection") or {}
        return (
            str(device.get("provider", "")).lower() == "demo"
            or str(device.get("protocol", "")).lower() == "demo"
            or str(connection.get("demoType", "")) in DEMO_DEVICE_TYPES
        )

    def demo_device_kind(device: dict[str, Any]) -> str:
        connection = device.get("connection") or {}
        kind = str(connection.get("demoType") or "")
        if kind in DEMO_DEVICE_TYPES:
            return kind
        type_code = device_type_code(device.get("type"))
        if type_code == "socket":
            return "demo_socket"
        if type_code == "motion_sensor":
            return "demo_motion_sensor"
        if type_code == "temperature_sensor":
            return "demo_temperature_sensor"
        if type_code == "leak_sensor":
            return "demo_leak_sensor"
        return "demo_light"

    def visual_room_demo_devices(room_id: str | None) -> list[dict[str, Any]]:
        if not room_id:
            return []
        return [
            device
            for device in data["devices"]
            if str(device.get("roomId")) == str(room_id) and is_demo_device(device)
        ]

    def merge_device_snapshot(updated: dict[str, Any]):
        updated_id = updated.get("id")
        for index, device in enumerate(data["devices"]):
            if device.get("id") == updated_id:
                data["devices"][index] = updated
                return
        data["devices"].append(updated)

    def visual_status_color(status: Any):
        raw = str(status)
        if raw.isdigit() and 200 <= int(raw) < 300:
            return "connected"
        if raw == "timeout":
            return "warning"
        return "no_connection"

    def demo_time_minutes() -> int:
        return int(state.get("visual_demo_time_minutes", DEMO_CLOCK_START_MINUTES) or 0) % (24 * 60)

    def format_demo_time(minutes: int | None = None) -> str:
        value = demo_time_minutes() if minutes is None else int(minutes) % (24 * 60)
        return f"{value // 60:02d}:{value % 60:02d}"

    def get_day_phase_by_time(minutes: int | None = None) -> str:
        value = demo_time_minutes() if minutes is None else int(minutes) % (24 * 60)
        if 6 * 60 <= value < 18 * 60:
            return "day"
        if 18 * 60 <= value < 22 * 60:
            return "evening"
        return "night"

    def demo_phase_title(phase: str | None = None) -> str:
        return {"day": "День", "evening": "Вечер", "night": "Ночь"}.get(phase or get_day_phase_by_time(), "День")

    def visual_scene_colors(phase: str | None = None) -> dict[str, str]:
        current_phase = phase or get_day_phase_by_time()
        dark = bool(state.get("dark"))
        if current_phase == "evening":
            return {
                "room": "#FFF7ED" if not dark else "#172033",
                "window": "#FDBA74",
                "window_alt": "#F97316",
                "text": "#7C2D12" if not dark else "#FED7AA",
            }
        if current_phase == "night":
            return {
                "room": "#DBEAFE" if not dark else "#0F172A",
                "window": "#1E293B",
                "window_alt": "#0F172A",
                "text": "#E0F2FE",
            }
        return {
            "room": c("field"),
            "window": "#BAE6FD",
            "window_alt": "#E0F2FE",
            "text": "#0F172A",
        }

    def add_visual_scene_log(action: str):
        logs = state.get("visual_scene_logs")
        if not isinstance(logs, list):
            logs = []
            state["visual_scene_logs"] = logs
        logs.insert(
            0,
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "kind": "LOCAL",
                "action": action,
                "demoTime": format_demo_time(),
            },
        )
        del logs[VISUAL_SCENE_LOG_LIMIT:]

    def update_visual_time_controls(phase_changed: bool = False):
        controls = state.get("visual_clock_controls")
        if isinstance(controls, dict):
            clock_text = controls.get("clock_text")
            phase_text = controls.get("phase_text")
            status_text = controls.get("status_text")
            clock_card = controls.get("clock_card")
            if clock_text is not None:
                clock_text.value = format_demo_time()
            if phase_text is not None:
                phase_text.value = demo_phase_title()
            if status_text is not None:
                status_text.value = "Время запущено" if state.get("visual_demo_time_running") else "Пауза"
            if clock_card is not None and getattr(clock_card, "page", None):
                try:
                    clock_card.update()
                except Exception:
                    pass

        scene_controls = state.get("visual_scene_controls")
        if phase_changed and isinstance(scene_controls, dict):
            phase = get_day_phase_by_time()
            colors = visual_scene_colors(phase)
            scene_container = scene_controls.get("scene_container")
            window_container = scene_controls.get("window_container")
            window_label = scene_controls.get("window_label")
            window_detail = scene_controls.get("window_detail")
            phase_icon = scene_controls.get("phase_icon")
            if scene_container is not None:
                scene_container.bgcolor = colors["room"]
            if window_container is not None:
                window_container.bgcolor = colors["window"]
            if phase_icon is not None:
                phase_icon.icon = ft.Icons.WB_SUNNY if phase == "day" else ft.Icons.NIGHTLIGHT
                phase_icon.color = colors["text"]
            if window_label is not None:
                window_label.value = demo_phase_title(phase)
                window_label.color = colors["text"]
            if window_detail is not None:
                window_detail.value = "06:00-17:59" if phase == "day" else "18:00-21:59" if phase == "evening" else "22:00-05:59"
                window_detail.color = colors["text"]
            if scene_container is not None and getattr(scene_container, "page", None):
                try:
                    scene_container.update()
                except Exception:
                    pass

        if phase_changed and int(state.get("tab", 0) or 0) == 6:
            render_current_view()

    def on_demo_time_changed(action: str | None = None):
        previous_phase = str(state.get("visual_day_phase") or "day")
        current_phase = get_day_phase_by_time()
        state["visual_day_phase"] = current_phase
        if action:
            add_visual_scene_log(action)
        if current_phase != previous_phase:
            add_visual_scene_log(f"phase changed: {current_phase}")
        update_visual_time_controls(phase_changed=current_phase != previous_phase)
        if current_phase != previous_phase and int(state.get("tab", 0) or 0) == 6 and is_authenticated():
            asyncio.create_task(trigger_visual_time_rules(current_phase, format_demo_time()))

    def set_demo_time(minutes: int, action: str | None = None):
        state["visual_demo_time_minutes"] = int(minutes) % (24 * 60)
        on_demo_time_changed(action)

    def advance_demo_time(minutes: int, action: str | None = None):
        set_demo_time(demo_time_minutes() + minutes, action)

    async def demo_clock_runner():
        try:
            while state.get("visual_demo_time_running"):
                await asyncio.sleep(DEMO_CLOCK_TICK_SECONDS)
                if not state.get("visual_demo_time_running"):
                    break
                advance_demo_time(1)
        finally:
            if state.get("visual_demo_clock_task") is asyncio.current_task():
                state["visual_demo_clock_task"] = None

    def ensure_demo_clock_task():
        task = state.get("visual_demo_clock_task")
        if isinstance(task, asyncio.Task) and not task.done():
            return
        state["visual_demo_clock_task"] = asyncio.create_task(demo_clock_runner())

    def start_demo_clock():
        if state.get("visual_demo_time_running"):
            update_visual_time_controls()
            return
        state["visual_demo_time_running"] = True
        add_visual_scene_log("demo-time started")
        ensure_demo_clock_task()
        update_visual_time_controls()
        render_current_view()

    def pause_demo_clock(add_log: bool = True):
        if not state.get("visual_demo_time_running"):
            update_visual_time_controls()
            return
        state["visual_demo_time_running"] = False
        task = state.get("visual_demo_clock_task")
        if isinstance(task, asyncio.Task) and not task.done():
            task.cancel()
        state["visual_demo_clock_task"] = None
        if add_log:
            add_visual_scene_log("demo-time paused")
        update_visual_time_controls()
        if int(state.get("tab", 0) or 0) == 6:
            render_current_view()

    def reset_demo_clock():
        state["visual_demo_time_running"] = False
        task = state.get("visual_demo_clock_task")
        if isinstance(task, asyncio.Task) and not task.done():
            task.cancel()
        state["visual_demo_clock_task"] = None
        set_demo_time(DEMO_CLOCK_START_MINUTES, "demo-time reset")
        render_current_view()

    def build_visual_scene_events() -> list[ft.Control]:
        logs = state.get("visual_scene_logs")
        entries = logs if isinstance(logs, list) else []
        controls: list[ft.Control] = [T("События сцены", weight=ft.FontWeight.BOLD), TM("Локальные действия, не backend endpointы", size=12)]
        if not entries:
            controls.append(TM("Локальных событий пока нет", size=12))
            return controls
        for entry in entries:
            controls.append(
                ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=c("field"),
                    border=ft.border.all(1, c("border")),
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            T(f"{entry.get('kind')} demo-time", size=12, weight=ft.FontWeight.BOLD),
                            TM(f"{entry.get('time')} · action: {entry.get('action')}", size=11),
                            TM(f"demoTime: {entry.get('demoTime')}", size=11),
                        ],
                    ),
                )
            )
        return controls

    def visual_automation_logs() -> list[dict[str, Any]]:
        logs = state.get("visual_automation_logs")
        if not isinstance(logs, list):
            logs = []
            state["visual_automation_logs"] = logs
        return logs

    def add_visual_automation_log(entry: dict[str, Any]):
        logs = visual_automation_logs()
        logs.insert(
            0,
            {
                "time": format_demo_time(),
                "kind": str(entry.get("kind") or "rule"),
                "name": str(entry.get("name") or "Автоматизация"),
                "action": str(entry.get("action") or ""),
                "status": str(entry.get("status") or "completed"),
                "message": str(entry.get("message") or ""),
            },
        )
        del logs[VISUAL_AUTOMATION_LOG_LIMIT:]

    def handle_visual_automation_result(result: Any):
        if not isinstance(result, dict):
            return
        for item in result.get("devices") or []:
            if isinstance(item, dict):
                merge_device_snapshot(item)
        for item in result.get("automations") or []:
            if isinstance(item, dict):
                add_visual_automation_log(item)

    async def refresh_visual_devices_state():
        await refresh_sections("devices", "logs")
        render_current_view()

    async def trigger_visual_event_rules(device: dict[str, Any], event_type: str, value: Any):
        room_id = device.get("roomId")
        device_id = device.get("id")
        if room_id is None or device_id is None:
            return
        payload = {
            "roomId": int(room_id),
            "sourceDeviceId": int(device_id),
            "eventType": event_type,
            "value": str(value).lower() if isinstance(value, bool) else str(value),
            "demoTime": format_demo_time(),
        }
        result = await visualization_api_request("post", "/api/visual-demo/events", payload)
        handle_visual_automation_result(result)

    async def trigger_visual_time_rules(phase: str, demo_time: str):
        room_id = visual_selected_room_id()
        if not room_id:
            return
        payload = {"roomId": int(room_id), "demoTime": demo_time, "phase": phase}
        result = await visualization_api_request("post", "/api/visual-demo/time", payload)
        handle_visual_automation_result(result)
        await refresh_visual_devices_state()

    async def trigger_visual_scenario(scenario_id: str):
        room_id = visual_selected_room_id()
        if not room_id:
            show_message("Выбери комнату")
            return
        pending = state.get("visual_pending_automation")
        if not isinstance(pending, set):
            pending = set()
            state["visual_pending_automation"] = pending
        if scenario_id in pending:
            return
        pending.add(scenario_id)
        render_current_view()
        try:
            result = await visualization_api_request("post", f"/api/visual-demo/scenarios/{scenario_id}", {"roomId": int(room_id)})
            handle_visual_automation_result(result)
            await refresh_visual_devices_state()
            show_message("Сценарий визуализации выполнен")
        except Exception as ex:
            add_visual_automation_log({"kind": "scenario", "name": scenario_id, "action": "error", "status": "error", "message": error_message(ex)})
            show_message(f"Не удалось выполнить сценарий визуализации: {error_message(ex)}")
        finally:
            pending.discard(scenario_id)
            render_current_view()

    def build_visual_rules_list() -> ft.Control:
        return ft.Column(
            spacing=6,
            controls=[
                T("Правила сцены", weight=ft.FontWeight.BOLD),
                *[
                    ft.Container(
                        padding=8,
                        border_radius=10,
                        bgcolor=c("field"),
                        border=ft.border.all(1, c("border")),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(spacing=2, controls=[T(rule["name"], size=12, weight=ft.FontWeight.BOLD), TM(f"{rule['trigger']} -> {rule['action']}", size=11)]),
                                status_chip("Активно", "enabled"),
                            ],
                        ),
                    )
                    for rule in VISUAL_RULES
                ],
            ],
        )

    def build_visual_scenarios_list() -> ft.Control:
        pending = state.get("visual_pending_automation")
        pending_set = pending if isinstance(pending, set) else set()
        return ft.Column(
            spacing=6,
            controls=[
                T("Сценарии сцены", weight=ft.FontWeight.BOLD),
                ft.Row(
                    wrap=True,
                    spacing=8,
                    run_spacing=8,
                    controls=[
                        ft.OutlinedButton(
                            scenario["name"],
                            icon=scenario["icon"],
                            disabled=scenario["id"] in pending_set,
                            on_click=async_click(lambda e, scenario_id=scenario["id"]: trigger_visual_scenario(str(scenario_id))),
                        )
                        for scenario in VISUAL_SCENARIOS
                    ],
                ),
            ],
        )

    def build_visual_automation_log_list() -> ft.Control:
        logs = visual_automation_logs()
        if not logs:
            return ft.Column(spacing=6, controls=[T("Последние срабатывания", weight=ft.FontWeight.BOLD), TM("Пока visual rules и scenarios не срабатывали", size=12)])
        return ft.Column(
            spacing=6,
            controls=[
                T("Последние срабатывания", weight=ft.FontWeight.BOLD),
                *[
                    ft.Container(
                        padding=8,
                        border_radius=10,
                        bgcolor=c("field"),
                        border=ft.border.all(1, c("border")),
                        content=ft.Column(
                            spacing=3,
                            controls=[
                                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[T(f"{item['time']} · {item['name']}", size=12, weight=ft.FontWeight.BOLD), status_chip(str(item["status"]), "connected" if item["status"] == "completed" else "warning")]),
                                TM(str(item.get("action") or item.get("message") or ""), size=11),
                            ],
                        ),
                    )
                    for item in logs[:5]
                ],
            ],
        )

    def build_visual_automation_panel() -> ft.Control:
        return ft.Container(
            padding=14,
            bgcolor=c("card"),
            border_radius=16,
            border=ft.border.all(1, c("border")),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(spacing=8, controls=[ft.Icon(ft.Icons.RULE, color=c("accent")), T("Автоматизации сцены", weight=ft.FontWeight.BOLD)]),
                    ft.ResponsiveRow(
                        columns=12,
                        spacing=12,
                        run_spacing=12,
                        controls=[
                            ft.Container(col={"sm": 12, "md": 4}, content=build_visual_rules_list()),
                            ft.Container(col={"sm": 12, "md": 4}, content=build_visual_scenarios_list()),
                            ft.Container(col={"sm": 12, "md": 4}, content=build_visual_automation_log_list()),
                        ],
                    ),
                ],
            ),
        )

    def build_visual_api_monitor() -> ft.Control:
        logs = state.get("visual_api_logs")
        entries = logs if isinstance(logs, list) else []
        entry_controls = []
        for entry in entries:
            body = str(entry.get("body") or "")
            error = str(entry.get("error") or "")
            entry_controls.append(
                ft.Container(
                    padding=10,
                    border_radius=12,
                    bgcolor=c("field"),
                    border=ft.border.all(1, c("border")),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    T(f"{entry.get('method')} {entry.get('path')}", weight=ft.FontWeight.BOLD, size=12),
                                    status_chip(str(entry.get("status")), visual_status_color(entry.get("status"))),
                                ],
                            ),
                            TM(f"{entry.get('time')} · {entry.get('durationMs')} мс", size=12),
                            *([TM(f"Body: {body}", size=11)] if body else []),
                            *([ft.Text(error, color="#DC2626", size=11)] if error else []),
                        ],
                    ),
                )
            )

        return ft.Container(
            width=390,
            padding=14,
            bgcolor=c("card"),
            border_radius=16,
            border=ft.border.all(1, c("border")),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            T("API-монитор", weight=ft.FontWeight.BOLD),
                            ft.Icon(ft.Icons.API, color=c("accent")),
                        ],
                    ),
                    TM("Только запросы из визуализации", size=12),
                    *(entry_controls or [TM("Запросов из визуализации пока нет", size=12)]),
                    ft.Divider(height=1, color=c("border")),
                    *build_visual_scene_events(),
                ],
            ),
        )

    async def toggle_visual_demo_device(device: dict[str, Any]):
        device_id = int(device.get("id", 0))
        if not device_id:
            return
        pending = state.get("visual_pending_devices")
        if not isinstance(pending, set):
            pending = set()
            state["visual_pending_devices"] = pending
        if device_id in pending:
            return
        pending.add(device_id)
        render_current_view()
        try:
            updated = await visualization_api_request("put", f"/api/devices/{device_id}/toggle")
            if isinstance(updated, dict):
                merge_device_snapshot(updated)
            await refresh_sections("devices", "logs")
        except Exception as ex:
            show_message(f"Не удалось изменить состояние устройства: {error_message(ex)}")
        finally:
            pending.discard(device_id)
            render_current_view()

    def visual_sensor_values() -> dict[str, dict[str, Any]]:
        values = state.get("visual_sensor_values")
        if not isinstance(values, dict):
            values = {}
            state["visual_sensor_values"] = values
        return values

    def visual_sensor_state(device: dict[str, Any]) -> dict[str, Any]:
        device_id = str(device.get("id", ""))
        values = visual_sensor_values()
        current = values.get(device_id)
        if isinstance(current, dict):
            return current

        connection = device.get("connection") or {}
        kind = demo_device_kind(device)
        initial: dict[str, Any] = {}
        if kind == "demo_temperature_sensor":
            raw = connection.get("temperature", 24)
            try:
                initial["temperature"] = int(float(str(raw).replace(",", ".")))
            except Exception:
                initial["temperature"] = 24
        if kind == "demo_motion_sensor":
            initial["motion"] = str(connection.get("motion", "false")).lower() == "true"
        if kind == "demo_leak_sensor":
            initial["leak"] = str(connection.get("leak", "false")).lower() == "true"
        values[device_id] = initial
        return initial

    def set_visual_sensor_value(device: dict[str, Any], key: str, value: Any):
        visual_sensor_state(device)[key] = value

    async def clear_visual_motion_later(device: dict[str, Any]):
        device_id = int(device.get("id", 0))
        await asyncio.sleep(1.2)
        pending = state.get("visual_pending_devices")
        if isinstance(pending, set) and device_id in pending:
            return
        set_visual_sensor_value(device, "motion", False)
        render_current_view()

    async def send_visual_demo_event(
        device: dict[str, Any],
        event_type: str,
        value: Any,
        success_message: str,
        state_update: tuple[str, Any] | None = None,
        message: str | None = None,
        after_success=None,
    ):
        device_id = int(device.get("id", 0))
        if not device_id:
            return
        pending = state.get("visual_pending_devices")
        if not isinstance(pending, set):
            pending = set()
            state["visual_pending_devices"] = pending
        if device_id in pending:
            return

        pending.add(device_id)
        render_current_view()
        clean_value = str(value).lower() if isinstance(value, bool) else str(value)
        payload = {
            "deviceId": device_id,
            "eventType": event_type,
            "value": clean_value,
            "source": "visual_demo",
            "message": message or success_message,
        }
        try:
            await visualization_api_request("post", "/api/events", payload)
            await trigger_visual_event_rules(device, event_type, value)
            if state_update is not None:
                set_visual_sensor_value(device, state_update[0], state_update[1])
            if after_success is not None:
                after_success()
            await refresh_sections("devices", "logs")
            show_message(success_message)
        except Exception as ex:
            show_message(f"Не удалось отправить событие: {error_message(ex)}")
        finally:
            pending.discard(device_id)
            render_current_view()

    def visual_pending_row(text: str) -> ft.Control:
        return ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[ft.ProgressRing(width=14, height=14, stroke_width=2), TM(text, size=11)],
        )

    def visual_device_header(config: dict[str, Any], device: dict[str, Any], icon_name: str = "icon", icon_color: str | None = None) -> list[ft.Control]:
        return [
            ft.Icon(config.get(icon_name, config["icon"]), size=34, color=icon_color or c("accent")),
            T(str(device.get("name", config["title"])), weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
        ]

    def render_demo_toggle_device(device: dict[str, Any], config: dict[str, Any], is_pending: bool) -> ft.Control:
        kind = demo_device_kind(device)
        is_on = bool(device.get("isOn"))
        lamp_on = kind == "demo_light" and is_on
        socket_on = kind == "demo_socket" and is_on
        bg = "#FEF3C7" if lamp_on else "#CCFBF1" if socket_on else c("card")
        icon_color = "#F59E0B" if lamp_on else c("accent") if socket_on else c("muted")
        status = config["status_on"] if is_on else config["status_off"]

        return ft.Container(
            width=200,
            height=176,
            padding=12,
            border_radius=16,
            bgcolor=bg,
            border=ft.border.all(1, c("border")),
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            on_click=async_click(lambda e, d=device: toggle_visual_demo_device(d)) if not is_pending else None,
            content=ft.Column(
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    *visual_device_header(config, device, "icon_on" if is_on else "icon", icon_color),
                    TM(status, size=12),
                    *([visual_pending_row("Отправка команды...")] if is_pending else []),
                ],
            ),
        )

    def render_demo_motion_sensor(device: dict[str, Any], config: dict[str, Any], is_pending: bool) -> ft.Control:
        detected = bool(visual_sensor_state(device).get("motion"))
        bg = "#FEF3C7" if detected else c("card")
        icon_color = "#F59E0B" if detected else c("accent")

        async def simulate_motion(_):
            await send_visual_demo_event(
                device,
                "motion",
                True,
                "visual_demo: сымитировано движение",
                ("motion", True),
                "visual_demo: сымитировано движение",
                after_success=lambda: asyncio.create_task(clear_visual_motion_later(device)),
            )

        return ft.Container(
            width=200,
            height=206,
            padding=12,
            border_radius=16,
            bgcolor=bg,
            border=ft.border.all(1, c("border")),
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    *visual_device_header(config, device, "icon_on" if detected else "icon", icon_color),
                    TM(config["status_on"] if detected else config["status_off"], size=12),
                    ft.OutlinedButton("Сымитировать движение", width=176, disabled=is_pending, on_click=async_click(simulate_motion)),
                    *([visual_pending_row("Отправка события...")] if is_pending else []),
                ],
            ),
        )

    def render_demo_temperature_sensor(device: dict[str, Any], config: dict[str, Any], is_pending: bool) -> ft.Control:
        current_temp = int(visual_sensor_state(device).get("temperature", config.get("default_temperature", 24)))

        async def change_temperature(delta: int):
            target = current_temp + delta
            if target < -30 or target > 60:
                show_message("Температура должна быть от -30 до 60 °C")
                return
            await send_visual_demo_event(
                device,
                "temperature_changed",
                target,
                "visual_demo: изменена температура",
                ("temperature", target),
                f"visual_demo: температура изменена на {target} °C",
            )

        return ft.Container(
            width=200,
            height=196,
            padding=12,
            border_radius=16,
            bgcolor=c("card"),
            border=ft.border.all(1, c("border")),
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    *visual_device_header(config, device, "icon", c("accent")),
                    T(f"{current_temp} °C", size=20, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.OutlinedButton("-1 °C", disabled=is_pending, on_click=async_click(lambda e: change_temperature(-1))),
                            ft.OutlinedButton("+1 °C", disabled=is_pending, on_click=async_click(lambda e: change_temperature(1))),
                        ],
                    ),
                    *([visual_pending_row("Отправка события...")] if is_pending else []),
                ],
            ),
        )

    def render_demo_leak_sensor(device: dict[str, Any], config: dict[str, Any], is_pending: bool) -> ft.Control:
        leak = bool(visual_sensor_state(device).get("leak"))
        bg = "#FEE2E2" if leak else c("card")
        icon_color = "#DC2626" if leak else c("accent")

        async def send_leak(value: bool):
            await send_visual_demo_event(
                device,
                "leak",
                value,
                "visual_demo: обнаружена протечка" if value else "visual_demo: протечка сброшена",
                ("leak", value),
                "visual_demo: обнаружена протечка" if value else "visual_demo: протечка сброшена",
            )

        return ft.Container(
            width=200,
            height=226,
            padding=12,
            border_radius=16,
            bgcolor=bg,
            border=ft.border.all(1, c("border")),
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                spacing=6,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    *visual_device_header(config, device, "icon_on" if leak else "icon", icon_color),
                    TM(config["status_on"] if leak else config["status_off"], size=12),
                    ft.OutlinedButton("Сымитировать протечку", width=176, disabled=is_pending or leak, on_click=async_click(lambda e: send_leak(True))),
                    ft.TextButton("Сбросить протечку", width=176, disabled=is_pending or not leak, on_click=async_click(lambda e: send_leak(False))),
                    *([visual_pending_row("Отправка события...")] if is_pending else []),
                ],
            ),
        )

    def build_visual_demo_device(device: dict[str, Any], index: int) -> ft.Control:
        kind = demo_device_kind(device)
        config = DEMO_DEVICE_TYPES.get(kind, DEMO_DEVICE_TYPES["demo_light"])
        pending = state.get("visual_pending_devices")
        is_pending = isinstance(pending, set) and int(device.get("id", 0)) in pending
        category = str(config.get("category", "toggle"))
        if category == "motion":
            return render_demo_motion_sensor(device, config, is_pending)
        if category == "temperature":
            return render_demo_temperature_sensor(device, config, is_pending)
        if category == "leak":
            return render_demo_leak_sensor(device, config, is_pending)
        return render_demo_toggle_device(device, config, is_pending)

    def build_demo_clock_controls() -> ft.Control:
        clock_text = T(format_demo_time(), size=22, weight=ft.FontWeight.BOLD)
        phase_text = TM(demo_phase_title(), size=12)
        status_text = TM("Время запущено" if state.get("visual_demo_time_running") else "Пауза", size=12)
        clock_card = ft.Container(
            padding=12,
            border_radius=16,
            bgcolor=c("card"),
            border=ft.border.all(1, c("border")),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SCHEDULE, color=c("accent")),
                    ft.Column(spacing=2, controls=[clock_text, phase_text, status_text]),
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.OutlinedButton("Старт", icon=ft.Icons.PLAY_ARROW, on_click=lambda e: start_demo_clock()),
                            ft.OutlinedButton("Пауза", icon=ft.Icons.PAUSE, on_click=lambda e: pause_demo_clock()),
                            ft.TextButton("+1 час", on_click=lambda e: (advance_demo_time(60, "demo-time advanced +1 hour"), render_current_view())),
                            ft.TextButton("+6 часов", on_click=lambda e: (advance_demo_time(360, "demo-time advanced +6 hours"), render_current_view())),
                            ft.TextButton("Сброс", icon=ft.Icons.RESTART_ALT, on_click=lambda e: reset_demo_clock()),
                        ],
                    ),
                ],
            ),
        )
        state["visual_clock_controls"] = {
            "clock_card": clock_card,
            "clock_text": clock_text,
            "phase_text": phase_text,
            "status_text": status_text,
        }
        return clock_card

    def build_day_night_window() -> ft.Control:
        phase = get_day_phase_by_time()
        colors = visual_scene_colors(phase)
        window_label = ft.Text(demo_phase_title(phase), color=colors["text"], weight=ft.FontWeight.BOLD, size=13)
        window_detail = ft.Text(
            "06:00-17:59" if phase == "day" else "18:00-21:59" if phase == "evening" else "22:00-05:59",
            color=colors["text"],
            size=11,
        )
        phase_icon = ft.Icon(ft.Icons.WB_SUNNY if phase == "day" else ft.Icons.NIGHTLIGHT, color=colors["text"], size=20)
        window_container = ft.Container(
            width=168,
            height=112,
            padding=10,
            border_radius=14,
            bgcolor=colors["window"],
            border=ft.border.all(2, c("border")),
            animate=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
                controls=[
                    phase_icon,
                    window_label,
                    window_detail,
                ],
            ),
        )
        scene_controls = state.get("visual_scene_controls")
        if not isinstance(scene_controls, dict):
            scene_controls = {}
            state["visual_scene_controls"] = scene_controls
        scene_controls.update(
            {
                "window_container": window_container,
                "window_label": window_label,
                "window_detail": window_detail,
                "phase_icon": phase_icon,
            }
        )
        return window_container

    def build_visual_room_scene(room_id: str | None, devices: list[dict[str, Any]]) -> ft.Control:
        positioned: list[ft.Control] = [
            ft.Container(
                left=24,
                top=20,
                content=build_day_night_window(),
            )
        ]
        for index, device in enumerate(devices):
            col = index % 3
            row = index // 3
            positioned.append(
                ft.Container(
                    left=28 + col * 220,
                    top=164 + row * 238,
                    content=build_visual_demo_device(device, index),
                )
            )
        scene_height = max(560, 300 + ((len(devices) + 2) // 3) * 238)
        scene_content = (
            ft.Stack(controls=positioned, height=scene_height)
            if devices
            else ft.Container(
                height=scene_height,
                content=ft.Stack(
                    height=scene_height,
                    controls=[
                        *positioned,
                        ft.Container(
                            left=220,
                            top=210,
                            width=360,
                            alignment=ft.Alignment(0, 0),
                            content=TM("В этой комнате пока нет демо-устройств."),
                        ),
                    ],
                ),
            )
        )
        phase = get_day_phase_by_time()
        scene_container = ft.Container(
            expand=True,
            padding=16,
            border_radius=18,
            bgcolor=visual_scene_colors(phase)["room"],
            border=ft.border.all(1, c("border")),
            animate=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            T("Комната", weight=ft.FontWeight.BOLD),
                            TM(f"Демо-устройств: {len(devices)} · {demo_phase_title(phase)}", size=12),
                        ],
                    ),
                    scene_content,
                ],
            ),
        )
        scene_controls = state.get("visual_scene_controls")
        if not isinstance(scene_controls, dict):
            scene_controls = {}
            state["visual_scene_controls"] = scene_controls
        scene_controls["scene_container"] = scene_container
        return scene_container

    def open_visual_demo_device_dialog():
        if not data["rooms"]:
            show_message("Сначала создай комнату")
            return
        selected_room = visual_selected_room_id()
        name_tf = field(label="Название устройства", hint_text="Например: Демо лампа")
        type_dd = dropdown(
            label="Тип устройства",
            value="demo_light",
            options=[ft.dropdown.Option(key, str(config["title"])) for key, config in DEMO_DEVICE_TYPES.items()],
        )
        room_dd = dropdown(label="Комната", value=selected_room, options=room_options())
        is_on_sw = ft.Switch(label="Включено", value=False)
        bind_live_validator(name_tf, lambda value: validators.require_safe_text(value, "Название устройства", 2, 80))

        def demo_connection_defaults(kind: str) -> dict[str, str]:
            connection = {"demoType": kind}
            if kind == "demo_motion_sensor":
                connection["motion"] = "false"
            if kind == "demo_temperature_sensor":
                connection["temperature"] = str(DEMO_DEVICE_TYPES[kind].get("default_temperature", 24))
            if kind == "demo_leak_sensor":
                connection["leak"] = "false"
            return connection

        def sync_demo_initial_state(_=None):
            config = DEMO_DEVICE_TYPES.get(str(type_dd.value), DEMO_DEVICE_TYPES["demo_light"])
            is_on_sw.visible = str(config.get("category")) == "toggle"
            page.update()

        type_dd.on_change = sync_demo_initial_state
        sync_demo_initial_state()

        async def save():
            try:
                clean_name = validators.require_safe_text(name_tf.value, "Название устройства", 2, 80)
                clean_kind = require_selected(type_dd.value, "Тип устройства", set(DEMO_DEVICE_TYPES.keys()))
                clean_room_id = require_selected(room_dd.value, "Комната", {str(room.get("id")) for room in data["rooms"]})
                config = DEMO_DEVICE_TYPES[clean_kind]
                stamp = int(datetime.now().timestamp() * 1000)
                payload = {
                    "name": clean_name,
                    "roomId": int(clean_room_id),
                    "room": None,
                    "isOn": bool(is_on_sw.value) if str(config.get("category")) == "toggle" else False,
                    "type": config["device_type"],
                    "provider": "demo",
                    "protocol": "demo",
                    "channel": "local",
                    "externalId": f"{clean_kind}-{stamp}",
                    "manufacturer": "CALHouse",
                    "model": config["model"],
                    "connection": demo_connection_defaults(clean_kind),
                }
                created = await visualization_api_request("post", "/api/devices", payload)
                if isinstance(created, dict):
                    merge_device_snapshot(created)
                state["visual_room_id"] = str(clean_room_id)
                close_dialog(dialog)
                await refresh_sections("devices", "logs")
                render_current_view()
                show_message("Демо-устройство добавлено")
            except Exception as ex:
                render_current_view()
                show_message(error_message(ex))

        dialog = ft.AlertDialog(
            modal=True,
            title=T("Добавить демо-устройство", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=520,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[name_tf, type_dd, room_dd, is_on_sw],
                ),
            ),
            actions=[
                ft.TextButton("Отмена", on_click=lambda e: close_dialog(dialog)),
                ft.ElevatedButton("Добавить", icon=ft.Icons.ADD, on_click=async_click(lambda e: run_button_action(e, save))),
            ],
        )
        show_dialog(dialog)

    def visualization_view() -> ft.Control:
        selected_room = visual_selected_room_id()
        room_dd = dropdown(label="Комната", value=selected_room, options=room_options(), width=280)

        def on_room_change(e):
            state["visual_room_id"] = e.control.value
            render_current_view()

        room_dd.on_change = on_room_change
        demo_devices = visual_room_demo_devices(selected_room)
        loading = loading_banner("rooms", "devices")
        state["visual_day_phase"] = get_day_phase_by_time()
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Визуализация дома", size=22, weight=ft.FontWeight.BOLD), TM("Интерактивная демо-комната с реальными backend endpointами")]),
                        ft.Row(spacing=10, controls=[room_dd, ft.ElevatedButton("Добавить демо-устройство", icon=ft.Icons.ADD_HOME, visible=is_admin(), on_click=lambda e: open_visual_demo_device_dialog())]),
                    ],
                ),
                build_demo_clock_controls(),
                build_visual_automation_panel(),
                *([loading] if loading else []),
                ft.Row(
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        build_visual_room_scene(selected_room, demo_devices),
                        build_visual_api_monitor(),
                    ],
                ),
                *([] if is_admin() else [TM("Добавление демо-устройств доступно администратору.", size=12)]),
            ],
        )

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
        loading = loading_banner(*current_tab_sections())

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=18,
            controls=[
                ft.Container(
                    padding=18,
                    border_radius=18,
                    bgcolor=c("hero_bg"),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            T("CALHouse", size=26, weight=ft.FontWeight.BOLD, color=c("hero_text")),
                            ft.Text(
                                "Привет)))))",
                                color=c("hero_muted"),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text("C - Calm", color=c("hero_muted"), size=13),
                                    ft.Text("A - Adaptive", color=c("hero_muted"), size=13),
                                    ft.Text("L - Live", color=c("hero_muted"), size=13),
                                ],
                            ),
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.ElevatedButton("Добавить устройство", icon=ft.Icons.ADD, visible=is_admin(), on_click=async_click(lambda e: run_button_action(e, lambda: open_device_dialog()))),
                                ],
                            ),
                        ],
                    ),
                ),
                *([loading] if loading else []),
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
                        stat_card("Логи", str(len(data["logs"])), ft.Icons.HISTORY, 7),
                    ],
                ),
                T("Последние события", size=18, weight=ft.FontWeight.BOLD),
                *log_controls,
            ],
        )

    def devices_view() -> ft.Control:
        device_cards = []
        shown_devices = visible_items("devices", data["devices"])
        for device in shown_devices:
            room_dd = dropdown(value=str(device.get("roomId")) if device.get("roomId") is not None else None, options=room_options(), width=220)
            status_control = status_chip(str(device.get("connectionStatus", "unknown")), device.get("connectionStatus"))
            power_control = bool_chip(bool(device.get("isOn")))
            message_control = TM(device.get("connectionMessage") or "", size=12)
            action_buttons = []
            if device_type_capabilities(device.get("type")).get("canToggle", True):
                action_buttons.append(ft.ElevatedButton("Toggle", icon=ft.Icons.POWER_SETTINGS_NEW, on_click=async_click(lambda e, device_id=device["id"], sc=status_control, pc=power_control, mc=message_control: run_button_action(e, lambda: toggle_device_card(device_id, sc, pc, mc)))))
            if is_admin():
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
                                    message_control,
                                ],
                            ),
                            ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                controls=[
                                    status_control,
                                    power_control,
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
                        visible=is_admin(),
                        spacing=10,
                        controls=[
                            room_dd,
                            ft.OutlinedButton("Переместить", icon=ft.Icons.SWAP_HORIZ, on_click=async_click(lambda e, device_id=device["id"], dd=room_dd: run_button_action(e, lambda: move_device(int(device_id), dd.value)))),
                        ],
                    ),
                )
            )
        loading = loading_banner("devices")
        more = show_more_button("devices", len(data["devices"]))
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Устройства", size=22, weight=ft.FontWeight.BOLD), TM("Подключение реальных устройств, тест связи и управление")]),
                        ft.Row(spacing=10, controls=([ft.ElevatedButton("Добавить", icon=ft.Icons.ADD, on_click=async_click(lambda e: run_button_action(e, lambda: open_device_dialog())))] if is_admin() else []) + [ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build(show_toast=True))))]),
                    ],
                ),
                *([loading] if loading else []),
                *(device_cards or [card(TM("Устройств пока нет"))]),
                *([more] if more else []),
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
                            ft.Row(visible=is_admin(), spacing=8, controls=[ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, r=room: open_room_dialog(r)), ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, r=room: delete_room(int(r["id"]), str(r.get("name", "Комната"))))]),
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

        loading = loading_banner("rooms", "devices")
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Комнаты и зоны", size=22, weight=ft.FontWeight.BOLD), TM("CRUD комнат и группировка устройств")]),
                        ft.Row(spacing=10, controls=([ft.ElevatedButton("Создать комнату", icon=ft.Icons.ADD, on_click=lambda e: open_room_dialog())] if is_admin() else []) + [ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("rooms", "devices", show_toast=True))))]),
                    ],
                ),
                *([loading] if loading else []),
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
                            ft.Row(visible=is_admin(), spacing=8, controls=[ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda e, s=scene: open_scene_dialog(s)), ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, s=scene: delete_scene(int(s["id"]), str(s.get("name", "Сценарий"))))]),
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

        loading = loading_banner("scenes")
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Сценарии", size=22, weight=ft.FontWeight.BOLD), TM("Ручные сценарии, которые могут запускаться и из правил, и по расписанию")]),
                        ft.Row(spacing=10, controls=([ft.ElevatedButton("Создать сценарий", icon=ft.Icons.AUTO_AWESOME, on_click=lambda e: open_scene_dialog())] if is_admin() else []) + [ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("scenes", show_toast=True))))]),
                    ],
                ),
                *([loading] if loading else []),
                *(scene_cards or [card(TM("Сценариев пока нет"))]),
            ],
        )

    def rules_view() -> ft.Control:
        rule_cards = []
        shown_rules = visible_items("rules", data["rules"])
        for rule in shown_rules:
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
                            ft.Row(spacing=8, controls=[status_chip("Активно" if rule.get("isEnabled") else "Выключено", "enabled" if rule.get("isEnabled") else "disabled"), ft.IconButton(ft.Icons.EDIT_OUTLINED, visible=is_admin(), on_click=lambda e, r=rule: open_rule_dialog(r)), ft.IconButton(ft.Icons.DELETE_OUTLINE, visible=is_admin(), on_click=lambda e, r=rule: delete_rule(int(r["id"]), str(r.get("name", "Правило"))))]),
                        ],
                    ),
                    TM(action_text, size=12),
                    TM(f"Последнее срабатывание: {fmt_dt(rule.get('lastTriggeredAt'))}", size=12),
                    TM(rule.get("lastTriggerMessage") or "", size=12),
                    ft.Row(visible=is_admin(), spacing=10, controls=[ft.ElevatedButton("Включить" if not rule.get("isEnabled") else "Выключить", icon=ft.Icons.TOGGLE_ON if rule.get("isEnabled") else ft.Icons.TOGGLE_OFF, on_click=async_click(lambda e, rid=rule["id"], enabled=not bool(rule.get("isEnabled")): run_button_action(e, lambda: set_rule_enabled(int(rid), enabled))))]),
                )
            )

        loading = loading_banner("rules")
        more = show_more_button("rules", len(data["rules"]))
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Правила", size=22, weight=ft.FontWeight.BOLD), TM("Если событие датчика подходит под условие, выполняется действие или сценарий")]),
                        ft.Row(spacing=10, controls=([ft.ElevatedButton("Создать правило", icon=ft.Icons.ADD, on_click=lambda e: open_rule_dialog())] if is_admin() else []) + [ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("rules", show_toast=True))))]),
                    ],
                ),
                *([loading] if loading else []),
                *(rule_cards or [card(TM("Правил пока нет"))]),
                *([more] if more else []),
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
                            ft.Row(spacing=8, controls=[status_chip("Активно" if schedule.get("isEnabled") else "Выключено", "enabled" if schedule.get("isEnabled") else "disabled"), ft.IconButton(ft.Icons.EDIT_OUTLINED, visible=is_admin(), on_click=lambda e, s=schedule: open_schedule_dialog(s)), ft.IconButton(ft.Icons.DELETE_OUTLINE, visible=is_admin(), on_click=lambda e, s=schedule: delete_schedule(int(s["id"]), str(s.get("name", "Расписание"))))]),
                        ],
                    ),
                    TM(action_text, size=12),
                    TM(f"Последний запуск: {fmt_dt(schedule.get('lastRunAt'))}", size=12),
                    TM(schedule.get("lastRunMessage") or "", size=12),
                    ft.Row(visible=is_admin(), spacing=10, controls=[ft.ElevatedButton("Включить" if not schedule.get("isEnabled") else "Выключить", icon=ft.Icons.TOGGLE_ON if schedule.get("isEnabled") else ft.Icons.TOGGLE_OFF, on_click=async_click(lambda e, sid=schedule["id"], enabled=not bool(schedule.get("isEnabled")): run_button_action(e, lambda: set_schedule_enabled(int(sid), enabled))))]),
                )
            )

        loading = loading_banner("schedules")
        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=4, controls=[T("Расписание", size=22, weight=ft.FontWeight.BOLD), TM("Автоматический запуск действий и сценариев по времени")]),
                        ft.Row(spacing=10, controls=([ft.ElevatedButton("Создать расписание", icon=ft.Icons.ADD, on_click=lambda e: open_schedule_dialog())] if is_admin() else []) + [ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("schedules", show_toast=True))))]),
                    ],
                ),
                *([loading] if loading else []),
                *(schedule_cards or [card(TM("Расписаний пока нет"))]),
            ],
        )

    def history_view() -> ft.Control:
        shown_logs = visible_items("logs", data["logs"])
        loading = loading_banner("logs")
        more = show_more_button("logs", len(data["logs"]))
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
                *([loading] if loading else []),
                *([
                    card(
                        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[T(str(log.get("message", "Событие")), weight=ft.FontWeight.BOLD), TM(fmt_dt(log.get("ts")), size=12)]),
                        TM(f"Тип: {log.get('eventType', 'EVENT')} · Источник: {log.get('source', 'api')}", size=12),
                        TM(f"deviceId={log.get('deviceId')} · sceneId={log.get('sceneId')} · runId={log.get('runId')}", size=12),
                    )
                    for log in shown_logs
                ] or [card(TM("Логи пока пустые"))]),
                *([more] if more else []),
            ],
        )

    async def apply_auth_result(result: dict[str, Any]):
        state["token"] = result.get("token")
        state["login"] = result.get("login", "")
        state["role"] = result.get("role", "User")
        state["tab"] = 0
        clear_data()
        if isinstance(state.get("loading_sections"), set):
            state["loading_sections"].update(current_tab_sections())
        build()

        async def load_after_auth(expected_token: str | None):
            try:
                await refresh_all()
            finally:
                if isinstance(state.get("loading_sections"), set):
                    state["loading_sections"].difference_update(current_tab_sections())
            if state.get("token") == expected_token:
                render_current_view()

        previous_task = state.get("auth_refresh_task")
        if isinstance(previous_task, asyncio.Task) and not previous_task.done():
            previous_task.cancel()
        state["auth_refresh_task"] = asyncio.create_task(load_after_auth(state.get("token")))

    def logout():
        previous_task = state.get("auth_refresh_task")
        if isinstance(previous_task, asyncio.Task) and not previous_task.done():
            previous_task.cancel()
        state["auth_refresh_task"] = None
        state["token"] = None
        state["login"] = ""
        state["role"] = ""
        state["tab"] = 0
        if isinstance(state.get("loading_sections"), set):
            state["loading_sections"].clear()
        if isinstance(state.get("refreshing_keys"), set):
            state["refreshing_keys"].clear()
        if isinstance(state.get("visual_api_logs"), list):
            state["visual_api_logs"].clear()
        if isinstance(state.get("visual_pending_devices"), set):
            state["visual_pending_devices"].clear()
        if isinstance(state.get("visual_sensor_values"), dict):
            state["visual_sensor_values"].clear()
        if isinstance(state.get("visual_scene_logs"), list):
            state["visual_scene_logs"].clear()
        if isinstance(state.get("visual_automation_logs"), list):
            state["visual_automation_logs"].clear()
        if isinstance(state.get("visual_pending_automation"), set):
            state["visual_pending_automation"].clear()
        clock_task = state.get("visual_demo_clock_task")
        if isinstance(clock_task, asyncio.Task) and not clock_task.done():
            clock_task.cancel()
        state["visual_demo_clock_task"] = None
        state["visual_demo_time_running"] = False
        state["visual_demo_time_minutes"] = DEMO_CLOCK_START_MINUTES
        state["visual_day_phase"] = "day"
        state["visual_room_id"] = None
        clear_data()
        build()
        show_message("Выход выполнен")

    def auth_view() -> ft.Control:
        auth_card_width = 620
        auth_content_width = auth_card_width - 48
        login_tf = field(label="Логин", hint_text="admin", width=auth_content_width, error_max_lines=3)
        password_tf = field(label="Пароль", password=True, can_reveal_password=True, width=auth_content_width, error_max_lines=3)
        confirm_tf = field(label="Повтор пароля", password=True, can_reveal_password=True, width=auth_content_width, error_max_lines=3)
        auth_error_text = ft.Text(
            "",
            color="#DC2626",
            size=12,
            visible=False,
            width=auth_content_width,
            no_wrap=False,
            overflow=ft.TextOverflow.VISIBLE,
        )

        def update_auth_error_controls():
            for control in (password_tf, confirm_tf, auth_error_text):
                try:
                    if getattr(control, "page", None):
                        control.update()
                except Exception:
                    pass

        def set_auth_error(message: str, control: ft.Control | None = None):
            if control is not None:
                set_control_error(control, message)
            auth_error_text.value = message
            auth_error_text.visible = True
            update_auth_error_controls()

        def clear_auth_error():
            if not auth_error_text.visible and get_control_error(password_tf) != "Неправильно введен логин или пароль":
                return
            if get_control_error(password_tf) == "Неправильно введен логин или пароль":
                set_control_error(password_tf, None)
            auth_error_text.value = ""
            auth_error_text.visible = False
            update_auth_error_controls()

        def clear_password_errors():
            changed = bool(auth_error_text.visible or get_control_error(password_tf) or get_control_error(confirm_tf))
            set_control_error(password_tf, None)
            set_control_error(confirm_tf, None)
            auth_error_text.value = ""
            auth_error_text.visible = False
            if changed:
                update_auth_error_controls()

        def validate_auth_login(value: Any) -> str:
            result = validators.clean(value)
            if not result:
                raise ValueError("Логин обязателен")
            if len(result) < 3 or len(result) > 50:
                raise ValueError("Логин должен быть от 3 до 50 символов")
            if not validators.CODE_RE.fullmatch(result):
                raise ValueError("Логин должен содержать только латиницу, цифры, точку, дефис и подчёркивание")
            return result

        def validate_auth_password(value: Any, label: str = "Пароль") -> str:
            result = str(value or "")
            if len(result) < 6 or len(result) > 100:
                raise ValueError(f"{label} должен быть от 6 до 100 символов")
            return result

        def validate_confirm_password(value: Any) -> str:
            result = validate_auth_password(value, "Повтор пароля")
            if result != (password_tf.value or ""):
                raise ValueError("Пароли должны совпадать")
            return result

        def validate_auth_control(control: ft.Control, validator) -> str | None:
            try:
                validator(getattr(control, "value", None))
                set_control_error(control, None)
                error = None
            except Exception as ex:
                error = str(ex)
                set_control_error(control, error)
            try:
                if getattr(control, "page", None):
                    control.update()
            except Exception:
                pass
            return error

        def ensure_auth_controls_valid(items: list[tuple[ft.Control, Any]]) -> bool:
            first_error = None
            for control, validator in items:
                error = validate_auth_control(control, validator)
                if error and first_error is None:
                    first_error = error
            if first_error:
                set_auth_error(first_error)
                return False
            auth_error_text.value = ""
            auth_error_text.visible = False
            update_auth_error_controls()
            return True

        def on_login_change(e):
            clear_auth_error()
            validate_auth_control(e.control, validate_auth_login)

        login_tf.on_change = on_login_change

        def on_password_change(e):
            clear_password_errors()

        password_tf.on_change = on_password_change

        def on_confirm_change(e):
            clear_password_errors()

        confirm_tf.on_change = on_confirm_change

        async def submit_login():
            clear_auth_error()
            if not ensure_auth_controls_valid(
                [
                    (login_tf, validate_auth_login),
                    (password_tf, validate_auth_password),
                    (confirm_tf, validate_confirm_password),
                ]
            ):
                return
            try:
                result = await api_request("post", "/api/auth/login", {"login": (login_tf.value or "").strip(), "password": password_tf.value or ""})
            except RuntimeError as ex:
                if "логин или пароль" in str(ex).lower():
                    set_auth_error("Неправильно введен логин или пароль", password_tf)
                    return
                raise
            await apply_auth_result(result or {})
            show_message("Вход выполнен")

        async def submit_register():
            clear_auth_error()
            if not ensure_auth_controls_valid(
                [
                    (login_tf, validate_auth_login),
                    (password_tf, validate_auth_password),
                    (confirm_tf, validate_confirm_password),
                ]
            ):
                return
            result = await api_request(
                "post",
                "/api/auth/register",
                {"login": (login_tf.value or "").strip(), "password": password_tf.value or "", "confirmPassword": confirm_tf.value or ""},
            )
            await apply_auth_result(result or {})
            show_message("Регистрация выполнена")

        return ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            content=ft.Container(
                width=auth_card_width,
                padding=24,
                bgcolor=c("card"),
                border=ft.border.all(1, c("border")),
                border_radius=16,
                content=ft.Column(
                    tight=True,
                    spacing=12,
                    controls=[
                        T("CALHouse", size=28, weight=ft.FontWeight.BOLD),
                        TM("Войдите или зарегистрируйтесь"),
                        login_tf,
                        password_tf,
                        confirm_tf,
                        auth_error_text,
                        ft.Row(
                            width=auth_content_width,
                            spacing=10,
                            controls=[
                                ft.ElevatedButton("Войти", icon=ft.Icons.LOGIN, expand=True, on_click=async_click(lambda e: run_button_action(e, submit_login))),
                                ft.OutlinedButton("Зарегистрироваться", icon=ft.Icons.PERSON_ADD, expand=True, on_click=async_click(lambda e: run_button_action(e, submit_register))),
                            ],
                        ),
                    ],
                ),
            ),
        )

    async def set_user_role(user_id: int, role: str):
        await api_request("put", f"/api/users/{user_id}/role", {"role": role})
        await refresh_sections("users", "logs")
        render_current_view()
        show_message("Роль пользователя обновлена")

    async def set_user_active(user_id: int, is_active: bool):
        await api_request("put", f"/api/users/{user_id}/active", {"isActive": is_active})
        await refresh_sections("users", "logs")
        render_current_view()
        show_message("Пользователь активирован" if is_active else "Пользователь заблокирован")

    def validate_admin_password(value: Any) -> str:
        result = str(value or "")
        if len(result) < 6 or len(result) > 100:
            raise ValueError("Новый пароль должен быть от 6 до 100 символов")
        return result

    async def reset_user_password(user_id: int, password_value: str):
        clean_password = validate_admin_password(password_value)
        await api_request("put", f"/api/users/{user_id}/password", {"password": clean_password, "confirmPassword": clean_password})
        await refresh_sections("users", "logs")
        render_current_view()
        show_message("Пароль сброшен")

    def users_admin_panel() -> ft.Control:
        if not is_admin():
            return ft.Container()

        def set_plain_control_error(control: ft.Control, message: str | None):
            set_control_error(control, message)
            try:
                if getattr(control, "page", None):
                    control.update()
            except Exception:
                pass

        def validate_password_field(control: ft.Control) -> bool:
            try:
                validate_admin_password(getattr(control, "value", None))
                set_plain_control_error(control, None)
                return True
            except Exception as ex:
                set_plain_control_error(control, str(ex))
                return False

        async def save_role(e, user_id: int, role_dd: ft.Dropdown):
            await run_button_action(e, lambda: set_user_role(user_id, role_dd.value or "User"))

        async def save_status(e, user_id: int, login: str, active_sw: ft.Switch):
            target_active = bool(active_sw.value)

            async def apply_status():
                await set_user_active(user_id, target_active)

            if not target_active:
                confirm_action("Заблокировать пользователя", f"Заблокировать пользователя «{login}»?", apply_status)
                return
            await run_button_action(e, apply_status)

        async def save_password(e, user_id: int, password_tf: ft.TextField):
            if not validate_password_field(password_tf):
                return
            await run_button_action(e, lambda: reset_user_password(user_id, password_tf.value or ""))

        user_cards = []
        for user in data["users"]:
            user_id = int(user.get("id", 0))
            login = str(user.get("login", ""))
            role = str(user.get("role", "User"))
            is_active_value = bool(user.get("isActive", True))
            role_dd = dropdown(value=role, width=260, options=[ft.dropdown.Option("Admin"), ft.dropdown.Option("User")])
            active_sw = ft.Switch(value=is_active_value)
            active_status_text = TM(f"Выбранный статус: {'Активен' if is_active_value else 'Заблокирован'}", size=12)
            password_tf = field(label="Новый пароль", password=True, can_reveal_password=True, width=280, error_max_lines=2)

            def on_active_preview(e, label=active_status_text):
                label.value = f"Выбранный статус: {'Активен' if e.control.value else 'Заблокирован'}"
                try:
                    label.update()
                except Exception:
                    pass

            def on_password_change(e):
                set_plain_control_error(e.control, None)

            active_sw.on_change = on_active_preview
            password_tf.on_change = on_password_change

            user_cards.append(
                ft.Container(
                    padding=14,
                    border_radius=12,
                    bgcolor=c("field"),
                    border=ft.border.all(1, c("border")),
                    content=ft.Column(
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            ft.ResponsiveRow(
                                columns=12,
                                spacing=12,
                                run_spacing=12,
                                controls=[
                                    ft.Container(
                                        col={"xs": 12, "sm": 12, "md": 6, "lg": 3},
                                        content=ft.Column(
                                            spacing=4,
                                            controls=[
                                                T(login, weight=ft.FontWeight.BOLD, size=16),
                                                TM(f"Текущая роль: {role}", size=12),
                                                status_chip("Активен" if is_active_value else "Заблокирован", "enabled" if is_active_value else "disabled"),
                                            ],
                                        ),
                                    ),
                                    ft.Container(
                                        col={"xs": 12, "sm": 12, "md": 6, "lg": 3},
                                        content=ft.Column(
                                            spacing=4,
                                            controls=[
                                                T("Изменить роль", weight=ft.FontWeight.BOLD),
                                                role_dd,
                                                TM("Admin может управлять пользователями и настройками", size=12),
                                                TM("User может управлять устройствами и сценариями", size=12),
                                                ft.OutlinedButton(
                                                    "Сохранить роль",
                                                    icon=ft.Icons.SAVE_OUTLINED,
                                                    on_click=async_click(lambda e, uid=user_id, dd=role_dd: save_role(e, uid, dd)),
                                                ),
                                            ],
                                        ),
                                    ),
                                    ft.Container(
                                        col={"xs": 12, "sm": 12, "md": 6, "lg": 3},
                                        content=ft.Column(
                                            spacing=4,
                                            controls=[
                                                T("Активность аккаунта", weight=ft.FontWeight.BOLD),
                                                ft.Row(spacing=8, wrap=True, controls=[active_sw, active_status_text]),
                                                ft.OutlinedButton(
                                                    "Сохранить статус",
                                                    icon=ft.Icons.VERIFIED_USER_OUTLINED,
                                                    on_click=async_click(lambda e, uid=user_id, login_value=login, sw=active_sw: save_status(e, uid, login_value, sw)),
                                                ),
                                            ],
                                        ),
                                    ),
                                    ft.Container(
                                        col={"xs": 12, "sm": 12, "md": 6, "lg": 3},
                                        content=ft.Column(
                                            spacing=4,
                                            controls=[
                                                T("Сброс пароля", weight=ft.FontWeight.BOLD),
                                                password_tf,
                                                ft.OutlinedButton(
                                                    "Сбросить пароль",
                                                    icon=ft.Icons.LOCK_RESET,
                                                    on_click=async_click(lambda e, uid=user_id, tf=password_tf: save_password(e, uid, tf)),
                                                ),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

        return ft.Container(
            padding=16,
            bgcolor=c("card"),
            border_radius=16,
            border=ft.border.all(1, c("border")),
            content=ft.Column(
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    T("Пользователи", weight=ft.FontWeight.BOLD),
                    TM("Управление ролями, статусом аккаунтов и сбросом паролей"),
                    *(user_cards or [TM("Пользователей пока нет")]),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        controls=[
                            ft.OutlinedButton("Обновить", icon=ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build("users", show_toast=True)))),
                        ],
                    ),
                ],
            ),
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
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                T("Настройки", size=22, weight=ft.FontWeight.BOLD),
                card(T("Интерфейс", weight=ft.FontWeight.BOLD), dark_sw, ft.ElevatedButton("Сохранить", on_click=save_settings)),
                users_admin_panel(),
            ],
        )

    nav = ft.NavigationBar(
        selected_index=0,
        bgcolor=c("nav"),
        indicator_color=c("nav_indicator"),
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Главная"),
            ft.NavigationBarDestination(icon=ft.Icons.FLASH_ON_OUTLINED, selected_icon=ft.Icons.FLASH_ON, label="Устройства"),
            ft.NavigationBarDestination(icon=ft.Icons.MEETING_ROOM, selected_icon=ft.Icons.MEETING_ROOM, label="Комнаты"),
            ft.NavigationBarDestination(icon=ft.Icons.AUTO_AWESOME, selected_icon=ft.Icons.AUTO_AWESOME, label="Сценарии"),
            ft.NavigationBarDestination(icon=ft.Icons.RULE, selected_icon=ft.Icons.RULE, label="Правила"),
            ft.NavigationBarDestination(icon=ft.Icons.SCHEDULE, selected_icon=ft.Icons.SCHEDULE, label="Расписание"),
            ft.NavigationBarDestination(icon=ft.Icons.HOME_WORK_OUTLINED, selected_icon=ft.Icons.ADD_HOME, label="Визуализация"),
            ft.NavigationBarDestination(icon=ft.Icons.HISTORY_OUTLINED, selected_icon=ft.Icons.HISTORY, label="История"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Настройки"),
        ],
    )

    async def on_nav_change(e: ft.ControlEvent):
        previous_tab = int(state.get("tab", 0) or 0)
        state["tab"] = int(e.control.selected_index)
        if previous_tab == 6 and state["tab"] != 6:
            pause_demo_clock(add_log=False)
        await render_current_view_animated(update_nav=True)

    nav.on_change = async_click(on_nav_change)

    def current_view() -> ft.Control:
        views = {
            0: home_view,
            1: devices_view,
            2: rooms_view,
            3: scenes_view,
            4: rules_view,
            5: schedules_view,
            6: visualization_view,
            7: history_view,
            8: settings_view,
        }
        return views.get(state["tab"], home_view)()

    def render_current_view(update_nav: bool = False):
        if not is_authenticated():
            build()
            return
        if update_nav:
            nav.selected_index = state["tab"]
        content.opacity = 1
        clear_pending_card_reveals()
        content.content = current_view()
        if getattr(content, "page", None):
            content.update()
            schedule_card_reveal()
            if update_nav:
                try:
                    nav.update()
                except Exception:
                    pass
        else:
            page.update()

    async def render_current_view_animated(update_nav: bool = False):
        if not is_authenticated():
            build()
            return
        if update_nav:
            nav.selected_index = state["tab"]
        clear_pending_card_reveals()
        content.content = current_view()
        content.opacity = 0
        if getattr(content, "page", None):
            content.update()
            schedule_card_reveal()
            if update_nav:
                try:
                    nav.update()
                except Exception:
                    pass
            await asyncio.sleep(0.01)
            content.opacity = 1
            content.update()
        else:
            content.opacity = 1
            page.update()

    def build():
        page.bgcolor = c("bg")
        if not is_authenticated():
            page.navigation_bar = None
            page.appbar = None
            content.opacity = 1
            clear_pending_card_reveals()
            content.content = auth_view()
            page.controls.clear()
            page.add(content)
            page.update()
            return

        page.navigation_bar = nav
        nav.bgcolor = c("nav")
        nav.indicator_color = c("nav_indicator")
        nav.selected_index = state["tab"]
        page.appbar = ft.AppBar(
            bgcolor=c("nav"),
            title=ft.Text("CALHouse", color=c("text"), weight=ft.FontWeight.BOLD),
            actions=[
                ft.Text(f"{state.get('login', '')} / {state.get('role', '')}", color=c("text")),
                ft.IconButton(ft.Icons.REFRESH, on_click=async_click(lambda e: run_button_action(e, lambda: refresh_and_build(show_toast=True))), icon_color=c("text")),
                ft.TextButton("Выйти", on_click=lambda e: logout()),
            ],
        )
        content.opacity = 1
        clear_pending_card_reveals()
        content.content = current_view()
        page.controls.clear()
        page.add(content)
        page.update()
        schedule_card_reveal()

    build()


ft.run(main)
