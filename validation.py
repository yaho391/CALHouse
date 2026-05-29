import json
import re
from urllib.parse import urlparse


SAFE_TEXT_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9 _.\-]+$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._\-]+$")
CODE_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
MQTT_TOPIC_RE = re.compile(r"^[A-Za-z0-9/_\-.]+$")
HOST_RE = re.compile(
    r"^((25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(25[0-5]|2[0-4]\d|1?\d?\d)$"
    r"|^([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)(\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)

BOOL_EVENTS = {"motion", "smoke", "water_leak", "door_open", "online", "offline"}
NUMERIC_EVENT_RANGES = {
    "temperature": (-50, 100),
    "humidity": (0, 100),
    "battery": (0, 100),
}
TEXT_EVENTS = {"power", "button_click", "state"}
ALLOWED_EVENTS = BOOL_EVENTS | set(NUMERIC_EVENT_RANGES) | TEXT_EVENTS
NUMERIC_OPERATORS = {"=", "!=", ">", ">=", "<", "<="}


def clean(value) -> str:
    return str(value or "").strip()


def reject_dangerous_text(value: str, label: str):
    lowered = value.lower()
    if (
        any(ord(ch) < 32 for ch in value)
        or any(ch in value for ch in ['\\', ';', '"', "<", ">"])
        or "script" in lowered
        or "--" in value
        or "/*" in value
        or "*/" in value
    ):
        raise ValueError(f"{label}: поле не должно содержать спецсимволы или script/html")


def require_safe_text(value, label: str, min_length: int, max_length: int, *, no_only_digits: bool = False) -> str:
    result = clean(value)
    if not result:
        raise ValueError(f"{label}: поле обязательно")
    if len(result) < min_length:
        raise ValueError(f"{label}: минимум {min_length} символа")
    if len(result) > max_length:
        raise ValueError(f"{label}: максимум {max_length} символов")
    reject_dangerous_text(result, label)
    if not SAFE_TEXT_RE.fullmatch(result):
        raise ValueError(f"{label}: разрешены буквы, цифры, пробел, дефис, подчёркивание и точка")
    if no_only_digits and result.replace(" ", "").isdigit():
        raise ValueError(f"{label}: значение не должно состоять только из цифр")
    return result


def optional_safe_text(value, label: str, min_length: int, max_length: int, *, no_only_digits: bool = False) -> str:
    result = clean(value)
    if not result:
        return ""
    return require_safe_text(result, label, min_length, max_length, no_only_digits=no_only_digits)


def optional_free_text(value, label: str, max_length: int) -> str:
    result = clean(value)
    if not result:
        return ""
    if len(result) > max_length:
        raise ValueError(f"{label}: максимум {max_length} символов")
    reject_dangerous_text(result, label)
    return result


def require_identifier(value, label: str = "Идентификатор") -> str:
    result = clean(value)
    if not result:
        raise ValueError(f"{label}: поле обязательно")
    if len(result) < 3 or len(result) > 100:
        raise ValueError(f"{label}: длина 3-100 символов")
    if not IDENTIFIER_RE.fullmatch(result):
        raise ValueError(f"{label}: только латиница, цифры, точка, дефис и подчёркивание, без пробелов")
    return result


def require_code(value, label: str, max_length: int = 80) -> str:
    result = clean(value)
    if not result:
        raise ValueError(f"{label}: поле обязательно")
    if len(result) > max_length:
        raise ValueError(f"{label}: максимум {max_length} символов")
    if not CODE_RE.fullmatch(result):
        raise ValueError(f"{label}: разрешены латиница, цифры, точка, дефис и подчёркивание")
    return result


def optional_code(value, label: str, max_length: int = 50) -> str:
    result = clean(value)
    if not result:
        return ""
    return require_code(result, label, max_length)


def require_selected(value, label: str, allowed: set[str] | None = None) -> str:
    result = clean(value)
    if not result:
        raise ValueError(f"{label}: нужно выбрать значение")
    if allowed is not None and result not in allowed:
        raise ValueError(f"{label}: выбрано недопустимое значение")
    return result


def require_hhmm(value) -> str:
    result = clean(value)
    if not re.fullmatch(r"\d{2}:\d{2}", result):
        raise ValueError("Время: нужен формат HH:mm")
    hour, minute = (int(part) for part in result.split(":"))
    if hour > 23 or minute > 59:
        raise ValueError("Время: часы 00-23, минуты 00-59")
    return result


def validate_port(value, label: str = "Port", *, required: bool = True) -> str:
    result = clean(value)
    if not result:
        if required:
            raise ValueError(f"{label}: поле обязательно")
        return ""
    if not result.isdigit():
        raise ValueError(f"{label}: нужно число от 1 до 65535")
    port = int(result)
    if port < 1 or port > 65535:
        raise ValueError(f"{label}: нужно число от 1 до 65535")
    return result


def validate_host(value, label: str = "Host / IP", *, required: bool = True) -> str:
    result = clean(value)
    if not result:
        if required:
            raise ValueError(f"{label}: поле обязательно")
        return ""
    if len(result) > 253 or "://" in result or "/" in result or any(ch.isspace() for ch in result):
        raise ValueError(f"{label}: укажи host или IP без протокола, пути и пробелов")
    if not HOST_RE.fullmatch(result):
        raise ValueError(f"{label}: нужен валидный IPv4, домен или hostname")
    return result


def validate_url(value, label: str = "URL", *, required: bool = True) -> str:
    result = clean(value)
    if not result:
        if required:
            raise ValueError(f"{label}: поле обязательно")
        return ""
    if len(result) > 253 or any(ch.isspace() for ch in result):
        raise ValueError(f"{label}: максимум 253 символа и без пробелов")
    parsed = urlparse(render_template_sample(result))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label}: нужен абсолютный HTTP/HTTPS URL")
    return result


def render_template_sample(value: str) -> str:
    return (
        value.replace("{{isOn}}", "true")
        .replace("{isOn}", "true")
        .replace("{{value}}", "true")
        .replace("{value}", "true")
        .replace("{{state}}", "ON")
        .replace("{state}", "ON")
        .replace("{{stateLower}}", "on")
        .replace("{stateLower}", "on")
    )


def validate_mqtt_topic(value, label: str = "Topic", *, required: bool = True) -> str:
    result = clean(value)
    if not result:
        if required:
            raise ValueError(f"{label}: поле обязательно")
        return ""
    if len(result) > 200:
        raise ValueError(f"{label}: максимум 200 символов")
    if " " in result or "#" in result or "+" in result:
        raise ValueError(f"{label}: без пробелов и wildcard #/+")
    if not MQTT_TOPIC_RE.fullmatch(result):
        raise ValueError(f"{label}: разрешены латиница, цифры, /, _, -, .")
    return result


def validate_json_object(value, label: str, *, required: bool = False) -> str:
    result = clean(value)
    if not result:
        if required:
            raise ValueError(f"{label}: поле обязательно")
        return ""
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError as ex:
        raise ValueError(f"{label}: нужен валидный JSON-объект") from ex
    if not isinstance(parsed, dict):
        raise ValueError(f"{label}: нужен JSON-объект")
    for header_name, header_value in parsed.items():
        if not clean(header_name) or re.search(r"[\s\r\n]", str(header_name)):
            raise ValueError(f"{label}: некорректное имя заголовка")
        if "\r" in str(header_value) or "\n" in str(header_value):
            raise ValueError(f"{label}: значения не должны содержать переносы строк")
    return result


def validate_connection_values(connection: dict[str, str], schema_fields: dict[str, dict] | None = None):
    schema_fields = schema_fields or {}
    for name, field_def in schema_fields.items():
        label = str(field_def.get("label") or name)
        if field_def.get("required") and not clean(connection.get(name, "")):
            raise ValueError(f"{label}: поле обязательно")

    for key, value in connection.items():
        if len(key) > 120 or re.search(r"\s", key):
            raise ValueError("Имя поля подключения некорректно")
        if len(value) > 8000:
            raise ValueError(f"{key}: максимум 8000 символов")

    if "host" in connection:
        validate_host(connection["host"], "Host / IP")
    if "port" in connection:
        validate_port(connection["port"], "Port")
    if "url" in connection:
        validate_url(connection["url"], "URL")
    if "snapshot_url" in connection:
        validate_url(connection["snapshot_url"], "URL снимка", required=False)
    if "path" in connection:
        path = clean(connection["path"])
        if len(path) > 512 or "://" in path or any(ch.isspace() or ord(ch) < 32 for ch in path):
            raise ValueError("Path: максимум 512 символов, без протокола, пробелов и управляющих символов")
    if "topic" in connection:
        validate_mqtt_topic(connection["topic"], "Topic")
    if "state_topic" in connection:
        validate_mqtt_topic(connection["state_topic"], "Topic состояния", required=False)
    if clean(connection.get("topic")) and clean(connection.get("state_topic")) and clean(connection["topic"]) == clean(connection["state_topic"]):
        raise ValueError("Topic состояния не должен совпадать с командным Topic")
    if "username" in connection:
        optional_safe_text(connection["username"], "Пользователь", 1, 50)
    for key, label in (("password", "Пароль / ключ устройства"), ("device_key", "Пароль / ключ устройства"), ("token", "Токен")):
        if key in connection and len(clean(connection[key])) > 200:
            raise ValueError(f"{label}: максимум 200 символов")
    if "method" in connection:
        method = clean(connection["method"]).upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            raise ValueError("HTTP-метод: допустимы GET, POST, PUT, PATCH, DELETE, HEAD")
    if "headers" in connection:
        validate_json_object(connection["headers"], "Заголовки JSON")
    if "entity_id" in connection:
        entity_id = clean(connection["entity_id"])
        if len(entity_id) > 120 or "." not in entity_id or any(ch.isspace() or ord(ch) < 32 for ch in entity_id):
            raise ValueError("Entity ID: нужен формат domain.object_id, например light.kitchen")
    for key in ("payload_on", "payload_off"):
        if key in connection:
            require_safe_text(connection[key], key, 1, 50)
    if clean(connection.get("payload_on")) and clean(connection.get("payload_off")) and clean(connection["payload_on"]) == clean(connection["payload_off"]):
        raise ValueError("Payload ON и Payload OFF не должны совпадать")


def validate_event_type(value) -> str:
    result = require_code(value, "Тип события", 50)
    if result not in ALLOWED_EVENTS:
        raise ValueError("Тип события: выбери поддерживаемый тип")
    return result


def validate_event_value(event_type, value, label: str = "Значение") -> str:
    event = validate_event_type(event_type)
    result = clean(value)
    if not result:
        raise ValueError(f"{label}: поле обязательно")
    reject_dangerous_text(result, label)
    lowered = result.lower()
    if event in BOOL_EVENTS:
        if lowered not in {"true", "false"}:
            raise ValueError(f"{label}: для {event} можно только true/false")
    elif event in NUMERIC_EVENT_RANGES:
        try:
            number = float(result.replace(",", "."))
        except ValueError as ex:
            raise ValueError(f"{label}: для {event} нужно число") from ex
        min_value, max_value = NUMERIC_EVENT_RANGES[event]
        if number < min_value or number > max_value:
            raise ValueError(f"{label}: для {event} диапазон {min_value}..{max_value}")
    elif event == "power":
        if lowered not in {"true", "false", "on", "off", "1", "0"}:
            raise ValueError(f"{label}: для power можно true/false или ON/OFF")
    else:
        optional_free_text(result, label, 500)
    return result


def validate_rule_operator(event_type, operator) -> str:
    event = validate_event_type(event_type)
    op = clean(operator)
    if not op:
        raise ValueError("Оператор: нужно выбрать значение")
    if event in BOOL_EVENTS and op not in {"=", "!="}:
        raise ValueError("Оператор: для boolean-событий доступны только = или !=")
    if event in NUMERIC_EVENT_RANGES and op not in NUMERIC_OPERATORS:
        raise ValueError("Оператор: для числовых событий доступны =, !=, >, >=, <, <=")
    if op == "contains" and event not in TEXT_EVENTS:
        raise ValueError("Оператор contains доступен только для строковых событий")
    return op
