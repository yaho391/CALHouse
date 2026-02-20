import flet as ft
import requests
from datetime import datetime, timedelta

# пока что надо
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

USER_EMAIL = "user@smarthome.mtp"
USER_ROLE = "Пользователь"
API_BASE = "http://localhost:5000"

devices = [
    {
        "id": 1,
        "name": "Термостат",
        "room": "Гостиная",
        "value": "22°C",
        "status": "online",
        "badge": None,
        "icon": "thermostat",
        "trend": "up",
    },
    {
        "id": 2,
        "name": "Освещение",
        "room": "Спальня",
        "value": "75%",
        "status": "online",
        "badge": None,
        "icon": "light",
        "trend": "flat",
    },
    {
        "id": 3,
        "name": "Камера",
        "room": "Входная дверь",
        "value": "100%",
        "status": "online",
        "badge": None,
        "icon": "camera",
        "trend": "flat",
    },
    {
        "id": 4,
        "name": "Энергопотребление",
        "room": "Весь дом",
        "value": "2.4 кВт",
        "status": "warning",
        "badge": "Предупреждение",
        "icon": "energy",
        "trend": "down",
    },
]

history_list = [
    {
        "ts": datetime.now() - timedelta(minutes=7),
        "user": "admin@smarthome.mtp",
        "action": "Изменение",
        "device": "Термостат гостиная",
        "details": "Температура изменена с 20°C на 22°C",
        "tag_color": "blue",
    },
    {
        "ts": datetime.now() - timedelta(minutes=9),
        "user": USER_EMAIL,
        "action": "Включение",
        "device": "Освещение кухня",
        "details": "Яркость установлена на 100%",
        "tag_color": "green",
    },
    {
        "ts": datetime.now() - timedelta(minutes=14),
        "user": "admin@smarthome.mtp",
        "action": "Создание",
        "device": 'Сценарий "Вечер"',
        "details": "Создан новый автоматический сценарий",
        "tag_color": "purple",
    },
    {
        "ts": datetime.now() - timedelta(minutes=18),
        "user": USER_EMAIL,
        "action": "Выключение",
        "device": "Кондиционер спальня",
        "details": "Устройство выключено пользователем",
        "tag_color": "gray",
    },
    {
        "ts": datetime.now() - timedelta(hours=2),
        "user": "Система",
        "action": "Автоматическое",
        "device": "Камера входная",
        "details": "Обнаружено движение, началась запись",
        "tag_color": "orange",
    },
]


def _c(hex_color: str):
    return hex_color


def badge(text: str, color: str):
    return ft.Container(
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
        border_radius=999,
        bgcolor=color,
        content=ft.Text(text, size=12, color=_c("#111111")),
    )


def chip(text: str):
    return ft.Container(
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
        border_radius=999,
        bgcolor=_c("#ffffff"),
        content=ft.Row(
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.PERSON, size=16, color=_c("#0f172a")),
                ft.Text(text, size=12, color=_c("#0f172a"), weight=ft.FontWeight.W_600),
            ],
        ),
    )


def card_container(content: ft.Control, padding=16):
    return ft.Container(
        padding=padding,
        border_radius=16,
        bgcolor=_c("#ffffff"),
        border=ft.border.all(1, _c("#e5e7eb")),
        content=content,
    )


def small_stat(title: str, value: str, icon: str):
    icon_map = {
        "devices": ft.Icons.DEVICES_OTHER,
        "energy": ft.Icons.BOLT,
    }
    return ft.Container(
        expand=True,
        padding=16,
        border_radius=16,
        bgcolor=_c("#ffffff"),
        border=ft.border.all(1, _c("#e5e7eb")),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(icon_map.get(icon, ft.Icons.INFO), size=18, color=_c("#0f172a")),
                                ft.Text(title, size=12, color=_c("#64748b")),
                            ],
                        ),
                        ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=_c("#0f172a")),
                    ],
                )
            ],
        ),
    )


def device_icon(kind: str):
    m = {
        "thermostat": ft.Icons.THERMOSTAT,
        "light": ft.Icons.LIGHTBULB_OUTLINE,
        "camera": ft.Icons.VIDEOCAM_OUTLINED,
        "energy": ft.Icons.BOLT,
    }
    return m.get(kind, ft.Icons.DEVICES_OTHER)


def status_dot(status: str):
    color = _c("#22c55e") if status == "online" else (_c("#f59e0b") if status == "warning" else _c("#94a3b8"))
    return ft.Container(width=8, height=8, border_radius=999, bgcolor=color)


def trend_icon(trend: str):
    if trend == "up":
        return ft.Icon(ft.Icons.TRENDING_UP, size=16, color=_c("#22c55e"))
    if trend == "down":
        return ft.Icon(ft.Icons.TRENDING_DOWN, size=16, color=_c("#ef4444"))
    return ft.Icon(ft.Icons.TRENDING_FLAT, size=16, color=_c("#94a3b8"))


def toast(page: ft.Page, text: str):
    page.snack_bar = ft.SnackBar(ft.Text(text))
    page.snack_bar.open = True
    page.update()


def main(page: ft.Page):
    page.title = "SmartHome UI"
    page.window_width = 1200
    page.window_height = 800
    page.window_resizable = True

    state = {
        "logged_in": False,
        "tab": 0,
        "history_mode": "list",  # list/table
        "dark": False,
        "notif_push": True,
        "notif_email": True,
        "notif_sound": True,
        "notif_security": True,
        "energy_reports": False,
    }

    device_items = [d.copy() for d in devices]

    def map_api_device(device: dict):
        name = str(device.get("name", "Устройство"))
        lname = name.lower()
        if "термо" in lname or "климат" in lname:
            icon = "thermostat"
        elif "свет" in lname or "ламп" in lname:
            icon = "light"
        elif "камер" in lname:
            icon = "camera"
        else:
            icon = "energy"

        is_on = bool(device.get("isOn", False))
        return {
            "id": int(device.get("id", 0)),
            "name": name,
            "room": str(device.get("room", "Неизвестно")),
            "value": "ON" if is_on else "OFF",
            "status": "online" if is_on else "offline",
            "badge": None,
            "icon": icon,
            "trend": "flat",
        }

    def load_devices_from_api(show_error: bool = False):
        nonlocal device_items
        try:
            response = requests.get(f"{API_BASE}/api/devices", timeout=5)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                device_items = [map_api_device(item) for item in data]
        except requests.RequestException:
            if show_error:
                toast(page, "API недоступен. Проверьте backend на http://localhost:5000")

    def toggle_device_via_api(device_id: int):
        try:
            response = requests.put(f"{API_BASE}/api/devices/{device_id}/toggle", timeout=5)
            response.raise_for_status()
            load_devices_from_api(show_error=True)
            toast(page, f"Устройство #{device_id} переключено")
            build_root()
        except requests.RequestException:
            toast(page, f"Не удалось переключить устройство #{device_id}")

    # темная тема (единая палитра)
    def palette():
        if state.get("dark", False):
            return {
                "BG": "#0b1020",
                "SURFACE": "#0f172a",
                "CARD": "#111827",
                "CARD2": "#0b1226",
                "BORDER": "#1f2a44",
                "TEXT": "#f8fafc",
                "MUTED": "#94a3b8",
                "FIELD": "#0b1226",
                "FIELD_TEXT": "#f8fafc",
                "FIELD_HINT": "#94a3b8",
                "TOPBAR": "#0b1020",
                "NAV": "#111827",
            }
        else:
            return {
                "BG": "#f3f4f6",
                "SURFACE": "#ffffff",
                "CARD": "#ffffff",
                "CARD2": "#ffffff",
                "BORDER": "#e5e7eb",
                "TEXT": "#0f172a",
                "MUTED": "#64748b",
                "FIELD": "#eef2f7",
                "FIELD_TEXT": "#0f172a",
                "FIELD_HINT": "#64748b",
                "TOPBAR": "#ffffff",
                "NAV": "#ffffff",
            }

    def C(key: str):
        return _c(palette()[key])

    def T(text, **kwargs):
        return ft.Text(text, color=kwargs.pop("color", C("TEXT")), **kwargs)

    def TM(text, **kwargs):
        return ft.Text(text, color=kwargs.pop("color", C("MUTED")), **kwargs)

    # хелперы (тематические)
    def badge2(text: str):
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=999,
            bgcolor=C("FIELD"),
            border=ft.border.all(1, C("BORDER")),
            content=ft.Text(text, size=12, color=C("TEXT"), weight=ft.FontWeight.W_600),
        )

    def chip2(text: str):
        # чип на градиенте оставляем светлым (как было), чтоб читалось
        return ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border_radius=999,
            bgcolor=_c("#ffffff"),
            content=ft.Row(
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.PERSON, size=16, color=_c("#0f172a")),
                    ft.Text(text, size=12, color=_c("#0f172a"), weight=ft.FontWeight.W_600),
                ],
            ),
        )

    def card2(content: ft.Control, padding=16):
        return ft.Container(
            padding=padding,
            border_radius=16,
            bgcolor=C("CARD"),
            border=ft.border.all(1, C("BORDER")),
            content=content,
        )

    def small_stat2(title: str, value: str, icon: str):
        icon_map = {"devices": ft.Icons.DEVICES_OTHER, "energy": ft.Icons.BOLT}
        return ft.Container(
            expand=True,
            padding=16,
            border_radius=16,
            bgcolor=C("CARD"),
            border=ft.border.all(1, C("BORDER")),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(icon_map.get(icon, ft.Icons.INFO), size=18, color=C("TEXT")),
                                    TM(title, size=12),
                                ],
                            ),
                            T(value, size=22, weight=ft.FontWeight.BOLD),
                        ],
                    )
                ],
            ),
        )

    def themed_field(**kwargs):
        return ft.TextField(
            bgcolor=C("FIELD"),
            color=C("FIELD_TEXT"),
            border_color=C("BORDER"),
            hint_style=ft.TextStyle(color=C("FIELD_HINT")),
            label_style=ft.TextStyle(color=C("MUTED")),
            
            **kwargs
        )

    def themed_dropdown(**kwargs):
        return ft.Dropdown(
            bgcolor=C("FIELD"),
            border_color=C("BORDER"),
            **kwargs
        )

    # login fields (оставил визуал как было, но текст читаемый)
    email_tf = ft.TextField(
        label="Email",
        hint_text="your@email.com",
        prefix_icon=ft.Icons.MAIL_OUTLINE,
        width=420,
        bgcolor=_c("#f3f4f6"),
        border_color=_c("#e5e7eb"),
        color=_c("#0f172a"),
    )
    pass_tf = ft.TextField(
        label="Пароль",
        password=True,
        can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        width=420,
        bgcolor=_c("#f3f4f6"),
        border_color=_c("#e5e7eb"),
        color=_c("#0f172a"),
    )

    demo_box = ft.Container(
        width=420,
        padding=12,
        border_radius=12,
        bgcolor=_c("#eff6ff"),
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Text("Демо аккаунты:", weight=ft.FontWeight.BOLD, color=_c("#1d4ed8")),
                ft.Text("👤  user@smarthome.mtp / user123", color=_c("#413e87")),
                ft.Text("🧑‍💼  admin@smarthome.mtp / admin123", color=_c("#413e87")),
            ],
        ),
    )

    def on_login(_):
        state["logged_in"] = True
        load_devices_from_api(show_error=True)
        build_root()

    login_view = ft.Container(
        expand=True,
        bgcolor=_c("#eaf1ff"),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=18,
            controls=[
                ft.Container(
                    width=52,
                    height=52,
                    border_radius=14,
                    bgcolor=_c("#2563eb"),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.HOME, color=_c("#ffffff")),
                ),
                ft.Text("SmartHome", size=30, weight=ft.FontWeight.BOLD, color=_c("#0f172a")),
                ft.Text("Управление умным домом", color=_c("#475569")),
                card_container(
                    ft.Column(
                        spacing=12,
                        controls=[
                            ft.Text("Вход в систему", size=16, weight=ft.FontWeight.BOLD, color=_c("#0f172a")),
                            ft.Text("Введите свои учетные данные для доступа", color=_c("#64748b")),
                            email_tf,
                            pass_tf,
                            demo_box,
                            ft.ElevatedButton(
                                "Войти",
                                width=420,
                                height=44,
                                bgcolor=_c("#0b1020"),
                                color=_c("#ffffff"),
                                on_click=on_login,
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[
                                    ft.Text("Нет аккаунта? ", color=_c("#64748b")),
                                    ft.TextButton("Зарегистрироваться", on_click=lambda e: toast(page, "Пока макет")),
                                ],
                            ),
                        ],
                    ),
                    padding=18,
                ),
            ],
        ),
    )

    content = ft.Container(expand=True, padding=20)

    def set_appbar_home():
        page.appbar = ft.AppBar(
            bgcolor=C("TOPBAR"),
            elevation=0,
            title=ft.Text("", color=C("TEXT")),
            actions=[
                ft.IconButton(
                    ft.Icons.NOTIFICATIONS_OUTLINED,
                    icon_color=C("MUTED"),
                    on_click=lambda e: toast(page, "Уведомления (макет)"),
                )
            ],
        )



    def header_gradient_block():
        grad = ft.LinearGradient(
            begin=ft.Alignment(0, 0),
            end=ft.Alignment(1, 0),
            colors=[_c("#2563eb"), _c("#9333ea")],
        )
        return ft.Container(
            padding=18,
            border_radius=18,
            gradient=grad,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Column(
                                spacing=6,
                                controls=[
                                    ft.Text("Добро пожаловать!", size=26, weight=ft.FontWeight.BOLD, color=_c("#ffffff")),
                                    ft.Text("user", color=_c("#e2e8f0")),
                                    chip2("Пользователь"),
                                ],
                            ),
                            ft.Icon(ft.Icons.NOTIFICATIONS_OUTLINED, color=_c("#ffffff")),
                        ],
                    ),
                    ft.Row(
                        spacing=14,
                        controls=[
                            small_stat2("Устройства", "12/14", "devices"),
                            small_stat2("Энергия", "2.4 кВт", "energy"),
                        ],
                    ),
                ],
            ),
        )

    def home_device_card(d):
        icon_bg = {
            "thermostat": _c("#fee2e2"),
            "light": _c("#fef9c3"),
            "camera": _c("#dbeafe"),
            "energy": _c("#dcfce7"),
        }.get(d["icon"], _c("#e2e8f0"))

        icon_color = {
            "thermostat": _c("#ef4444"),
            "light": _c("#f59e0b"),
            "camera": _c("#2563eb"),
            "energy": _c("#16a34a"),
        }.get(d["icon"], _c("#0f172a"))

        top_right = status_dot(
            "online"
            if d["status"] == "online"
            else ("warning" if d["status"] == "warning" else "offline")
        )

        return ft.Container(
            expand=True,
            padding=16,
            border_radius=16,
            bgcolor=C("CARD"),
            border=ft.border.all(1, C("BORDER")),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=12,
                                bgcolor=icon_bg,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(device_icon(d["icon"]), size=18, color=icon_color),
                            ),
                            top_right,
                        ],
                    ),
                    T(d["name"], size=16, weight=ft.FontWeight.BOLD),
                    TM(d["room"]),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            T(d["value"], size=22, weight=ft.FontWeight.BOLD),
                            trend_icon(d["trend"]),
                        ],
                    ),
                ],
            ),
        )

    def home_view():
        set_appbar_home()

        grid = ft.Column(
            spacing=12,
            controls=[
                *[
                    ft.Row(spacing=12, controls=[home_device_card(d) for d in device_items[i:i+2]])
                    for i in range(0, len(device_items), 2)
                ],
            ],
        )

        quick_actions = ft.Row(
            spacing=12,
            controls=[
                ft.Container(
                    expand=True,
                    padding=14,
                    border_radius=14,
                    bgcolor=C("CARD"),
                    border=ft.border.all(1, C("BORDER")),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                        controls=[ft.Icon(ft.Icons.SCHEDULE, color=C("TEXT")), T("Сценарии", weight=ft.FontWeight.BOLD)],
                    ),
                    on_click=lambda e: toast(page, "Сценарии (макет)"),
                ),
                ft.Container(
                    expand=True,
                    padding=14,
                    border_radius=14,
                    bgcolor=C("CARD"),
                    border=ft.border.all(1, C("BORDER")),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                        controls=[ft.Icon(ft.Icons.BOLT, color=C("TEXT")), T("Энергия", weight=ft.FontWeight.BOLD)],
                    ),
                    on_click=lambda e: toast(page, "Энергия (макет)"),
                ),
            ],
        )

        events = ft.Column(
            spacing=10,
            controls=[
                card2(
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=12,
                                bgcolor=_c("#fef9c3"),
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(ft.Icons.NOTIFICATIONS, color=_c("#f59e0b"), size=18),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    T("Высокое энергопотребление", weight=ft.FontWeight.BOLD),
                                    TM("5 мин назад", size=12),
                                ],
                            ),
                        ],
                    ),
                    padding=14,
                ),
                card2(
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=12,
                                bgcolor=_c("#dbeafe"),
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(ft.Icons.VIDEOCAM, color=_c("#2563eb"), size=18),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    T("Камера обнаружила движение", weight=ft.FontWeight.BOLD),
                                    TM("15 мин назад", size=12),
                                ],
                            ),
                        ],
                    ),
                    padding=14,
                ),
                card2(
                    ft.Row(
                        spacing=12,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=12,
                                bgcolor=_c("#dcfce7"),
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(ft.Icons.CHECK_CIRCLE, color=_c("#16a34a"), size=18),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    T('Активирован сценарий "Ночной режим"', weight=ft.FontWeight.BOLD),
                                    TM("2 часа назад", size=12),
                                ],
                            ),
                        ],
                    ),
                    padding=14,
                ),
            ],
        )

        content.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=18,
            controls=[
                header_gradient_block(),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        T("Устройства", size=18, weight=ft.FontWeight.BOLD),
                        ft.TextButton("Все  >", on_click=lambda e: (state.update(tab=1), build_root())),
                    ],
                ),
                grid,
                T("Быстрые действия", size=18, weight=ft.FontWeight.BOLD),
                quick_actions,
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        T("Последние события", size=18, weight=ft.FontWeight.BOLD),
                        ft.TextButton("Все  >", on_click=lambda e: (state.update(tab=2), build_root())),
                    ],
                ),
                events,
                ft.Container(height=10),
            ],
        )
        page.update()

    def devices_view():
        set_appbar_home()

        search = themed_field(
            hint_text="Поиск по названию или комнате...",
            prefix_icon=ft.Icons.SEARCH,
        )
        dd_type = themed_dropdown(
            value="Все типы",
            options=[
                ft.dropdown.Option("Все типы"),
                ft.dropdown.Option("Свет"),
                ft.dropdown.Option("Климат"),
                ft.dropdown.Option("Камера"),
            ],
            expand=True,
        )
        dd_status = themed_dropdown(
            value="Все статусы",
            options=[
                ft.dropdown.Option("Все статусы"),
                ft.dropdown.Option("Онлайн"),
                ft.dropdown.Option("Предупреждение"),
                ft.dropdown.Option("Оффлайн"),
            ],
            expand=True,
        )

        seg_grid = ft.ElevatedButton(
            "Сетка",
            expand=True,
            bgcolor=_c("#0b1020"),
            color=_c("#ffffff"),
            on_click=lambda e: toast(page, "Пока макет (сетку можно сделать позже)"),
        )
        seg_table = ft.OutlinedButton("Таблица", expand=True, on_click=lambda e: toast(page, "Пока макет"))

        add_btn = ft.ElevatedButton(
            "Добавить устройство",
            icon=ft.Icons.ADD,
            bgcolor=_c("#0b1020"),
            color=_c("#ffffff"),
            height=44,
            on_click=lambda e: toast(page, "Добавление (макет)"),
        )
        refresh_btn = ft.OutlinedButton(
            "Обновить",
            icon=ft.Icons.REFRESH,
            on_click=lambda e: (load_devices_from_api(show_error=True), build_root()),
            height=44,
        )

        def device_row(d):
            badge_text = "Онлайн" if d["status"] == "online" else ("Предупреждение" if d["status"] == "warning" else "Оффлайн")
            badge_bg = _c("#dcfce7") if d["status"] == "online" else (_c("#fef3c7") if d["status"] == "warning" else _c("#e2e8f0"))
            badge_fg = _c("#16a34a") if d["status"] == "online" else (_c("#b45309") if d["status"] == "warning" else _c("#475569"))

            return ft.Container(
                padding=16,
                border_radius=16,
                bgcolor=C("CARD"),
                border=ft.border.all(1, C("BORDER")),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=12,
                                    controls=[
                                        ft.Container(
                                            width=44,
                                            height=44,
                                            border_radius=14,
                                            bgcolor=C("FIELD"),
                                            alignment=ft.Alignment(0, 0),
                                            content=ft.Icon(device_icon(d["icon"]), color=_c("#2563eb")),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            controls=[
                                                T(d["name"], size=16, weight=ft.FontWeight.BOLD),
                                                TM(d["room"], size=12),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Container(
                                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                    border_radius=999,
                                    bgcolor=badge_bg,
                                    content=ft.Text(badge_text, size=12, color=badge_fg, weight=ft.FontWeight.W_600),
                                ),
                            ],
                        ),
                        T(d["value"], size=28, weight=ft.FontWeight.BOLD),
                        TM("Обновлено: 2026-01-23 09:15", size=12),
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.ElevatedButton(
                                    "Toggle",
                                    icon=ft.Icons.POWER_SETTINGS_NEW,
                                    expand=True,
                                    on_click=lambda e, device_id=d["id"]: toggle_device_via_api(device_id),
                                ),
                            ],
                        ),
                    ],
                ),
            )

        content.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                T("Управление устройствами", size=22, weight=ft.FontWeight.BOLD),
                TM(f"Всего устройств: {len(device_items)}"),
                search,
                ft.Row(spacing=12, controls=[dd_type, dd_status]),
                ft.Row(spacing=12, controls=[seg_grid, seg_table]),
                ft.Row(spacing=12, controls=[add_btn, refresh_btn]),
                *[device_row(d) for d in device_items],
                ft.Container(height=10),
            ],
        )
        page.update()

    def history_view():
        set_appbar_home()

        search = themed_field(
            hint_text="Поиск по пользователю, устройству или деталям...",
            prefix_icon=ft.Icons.SEARCH,
        )
        dd_actions = themed_dropdown(
            value="Все действия",
            options=[
                ft.dropdown.Option("Все действия"),
                ft.dropdown.Option("Изменение"),
                ft.dropdown.Option("Включение"),
                ft.dropdown.Option("Выключение"),
                ft.dropdown.Option("Создание"),
                ft.dropdown.Option("Предупреждение"),
            ],
            expand=True,
        )

        def set_history_mode(mode: str):
            state["history_mode"] = mode
            build_root()

        btn_list = ft.ElevatedButton(
            "Список",
            expand=True,
            bgcolor=_c("#0b1020") if state["history_mode"] == "list" else None,
            color=_c("#ffffff") if state["history_mode"] == "list" else None,
            on_click=lambda e: set_history_mode("list"),
        )
        btn_table = ft.ElevatedButton(
            "Таблица",
            expand=True,
            bgcolor=_c("#0b1020") if state["history_mode"] == "table" else None,
            color=_c("#ffffff") if state["history_mode"] == "table" else None,
            on_click=lambda e: set_history_mode("table"),
        )

        stats = ft.Row(
            spacing=12,
            controls=[
                card2(
                    ft.Column(
                        [T("12", size=22, weight=ft.FontWeight.BOLD), TM("Записей", size=12)],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=18,
                ),
                card2(
                    ft.Column(
                        [T("3", size=22, weight=ft.FontWeight.BOLD), TM("Пользователей", size=12)],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=18,
                ),
                card2(
                    ft.Column(
                        [T("11", size=22, weight=ft.FontWeight.BOLD), TM("Устройств", size=12)],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=18,
                ),
            ],
        )

        def tag_color(tc: str):
            return {
                "blue": _c("#dbeafe"),
                "green": _c("#dcfce7"),
                "purple": _c("#f3e8ff"),
                "gray": _c("#e2e8f0"),
                "orange": _c("#ffedd5"),
            }.get(tc, _c("#e2e8f0"))

        def tag_text_color(tc: str):
            return {
                "blue": _c("#2563eb"),
                "green": _c("#16a34a"),
                "purple": _c("#9333ea"),
                "gray": _c("#334155"),
                "orange": _c("#c2410c"),
            }.get(tc, _c("#334155"))

        def history_item(x):
            return ft.Container(
                padding=16,
                border_radius=16,
                bgcolor=C("CARD"),
                border=ft.border.all(1, C("BORDER")),
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        ft.Container(
                                            padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                            border_radius=999,
                                            bgcolor=tag_color(x["tag_color"]),
                                            content=ft.Text(
                                                x["action"],
                                                size=12,
                                                color=tag_text_color(x["tag_color"]),
                                                weight=ft.FontWeight.W_600,
                                            ),
                                        ),
                                        T(x["device"], weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Icon(ft.Icons.PERSON, size=16, color=_c("#2563eb")),
                                        TM(x["user"]),
                                    ],
                                ),
                            ],
                        ),
                        T(x["details"], color=C("TEXT")),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=C("MUTED")),
                                TM(x["ts"].strftime("%Y-%m-%d %H:%M:%S"), size=12),
                            ],
                        ),
                    ],
                ),
            )

        def history_table():
            rows = []
            for x in history_list:
                rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(x["ts"].strftime("%Y-%m-%d %H:%M:%S"), color=C("TEXT"))),
                            ft.DataCell(ft.Text(x["user"], color=C("TEXT"))),
                            ft.DataCell(ft.Text(x["action"], color=C("TEXT"))),
                            ft.DataCell(ft.Text(x["device"], color=C("TEXT"))),
                            ft.DataCell(ft.Text(x["details"], color=C("TEXT"))),
                        ]
                    )
                )

            return ft.Container(
                padding=0,
                border_radius=16,
                bgcolor=C("CARD"),
                border=ft.border.all(1, C("BORDER")),
                content=ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Время", color=C("TEXT"))),
                        ft.DataColumn(ft.Text("Пользователь", color=C("TEXT"))),
                        ft.DataColumn(ft.Text("Действие", color=C("TEXT"))),
                        ft.DataColumn(ft.Text("Устройство", color=C("TEXT"))),
                        ft.DataColumn(ft.Text("Детали", color=C("TEXT"))),
                    ],
                    rows=rows,
                    heading_row_color=C("FIELD"),
                    data_row_min_height=44,
                    data_row_max_height=64,
                ),
            )

        list_or_table = (
            ft.Column(spacing=12, controls=[history_item(x) for x in history_list])
            if state["history_mode"] == "list"
            else history_table()
        )

        content.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                T("История изменений", size=22, weight=ft.FontWeight.BOLD),
                TM("Аудит всех действий в системе"),
                search,
                ft.Row(
                    spacing=12,
                    controls=[
                        dd_actions,
                        ft.OutlinedButton("Экспорт", icon=ft.Icons.DOWNLOAD, on_click=lambda e: toast(page, "Экспорт (макет)")),
                    ],
                ),
                ft.Row(spacing=12, controls=[btn_list, btn_table]),
                stats,
                list_or_table,
                ft.Container(height=10),
            ],
        )
        page.update()

    def settings_view():
        set_appbar_home()

        def toggle_dark(e):
            state["dark"] = e.control.value
            build_root()

        def sw(title, subtitle, key):
            def _handler(e):
                state[key] = e.control.value
                page.update()

            value = state[key]
            on_change = toggle_dark if key == "dark" else _handler

            return ft.Container(
                padding=16,
                border_radius=16,
                bgcolor=C("CARD"),
                border=ft.border.all(1, C("BORDER")),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            controls=[
                                T(title, weight=ft.FontWeight.BOLD),
                                TM(subtitle, size=12),
                            ],
                        ),
                        ft.Switch(value=value, on_change=on_change),
                    ],
                ),
            )

        profile = ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=C("CARD"),
            border=ft.border.all(1, C("BORDER")),
            content=ft.Row(
                spacing=12,
                controls=[
                    ft.Container(
                        width=46,
                        height=46,
                        border_radius=999,
                        bgcolor=C("FIELD"),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(ft.Icons.PERSON, color=_c("#2563eb")),
                    ),
                    ft.Column(
                        spacing=2,
                        controls=[
                            T("user", weight=ft.FontWeight.BOLD),
                            TM(USER_EMAIL),
                        ],
                    ),
                    ft.Container(expand=True),
                    badge2(USER_ROLE),
                ],
            ),
        )

        sec_block = ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=C("CARD"),
            border=ft.border.all(1, C("BORDER")),
            content=ft.Column(
                spacing=10,
                controls=[
                    T("Безопасность", weight=ft.FontWeight.BOLD),
                    ft.OutlinedButton("Изменить пароль", icon=ft.Icons.LOCK_OUTLINE, on_click=lambda e: toast(page, "Пока макет")),
                    ft.OutlinedButton("Двухфакторная аутентификация", icon=ft.Icons.PHONE_ANDROID, on_click=lambda e: toast(page, "Пока макет")),
                    ft.OutlinedButton("Активные сессии", icon=ft.Icons.PUBLIC, on_click=lambda e: toast(page, "Пока макет")),
                ],
            ),
        )

        data_block = ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=C("CARD"),
            border=ft.border.all(1, C("BORDER")),
            content=ft.Column(
                spacing=10,
                controls=[
                    T("Данные и конфиденциальность", weight=ft.FontWeight.BOLD),
                    ft.OutlinedButton("Экспортировать данные", icon=ft.Icons.MAIL_OUTLINE, on_click=lambda e: toast(page, "Экспорт (макет)")),
                    ft.Container(
                        padding=14,
                        border_radius=12,
                        bgcolor=_c("#fef9c3"),
                        content=ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.INFO_OUTLINE, color=_c("#b45309")),
                                ft.Text("Важно: бойтесь мошенников.", color=_c("#7c2d12")),
                            ],
                        ),
                    ),
                ],
            ),
        )

        content.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=14,
            controls=[
                T("Настройки", size=22, weight=ft.FontWeight.BOLD),
                TM("Управление параметрами системы"),
                profile,
                T("Внешний вид", size=16, weight=ft.FontWeight.BOLD),
                sw("Темная тема", "Изменить цветовую схему интерфейса", "dark"),
                T("Уведомления", size=16, weight=ft.FontWeight.BOLD),
                sw("Push-уведомления", "Получать уведомления на устройстве", "notif_push"),
                sw("Email уведомления", "Получать уведомления на почту", "notif_email"),
                sw("Звуковые уведомления", "Воспроизводить звук при уведомлениях", "notif_sound"),
                sw("Уведомления безопасности", "Критические события безопасности", "notif_security"),
                sw("Отчеты об энергии", "Еженедельные отчеты о потреблении", "energy_reports"),
                T("Безопасность", size=16, weight=ft.FontWeight.BOLD),
                sec_block,
                data_block,
                ft.ElevatedButton(
                    "Выйти из системы",
                    icon=ft.Icons.LOGOUT,
                    bgcolor=_c("#dc2626"),
                    color=_c("#ffffff"),
                    height=44,
                    on_click=lambda e: do_logout(),
                ),
                ft.OutlinedButton(
                    "Удалить аккаунт",
                    icon=ft.Icons.DELETE_FOREVER,
                    on_click=lambda e: toast(page, "Удаление (макет)"),
                ),
                ft.Container(height=6),
                TM("SmartHome v1.0.0", text_align=ft.TextAlign.CENTER),
                TM("© 2026 Все права защищены", text_align=ft.TextAlign.CENTER),
                ft.Container(height=10),
            ],
        )
        page.update()

    nav = ft.NavigationBar(
        selected_index=0,
        bgcolor=C("NAV"),
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Главная"),
            ft.NavigationBarDestination(icon=ft.Icons.FLASH_ON_OUTLINED, selected_icon=ft.Icons.FLASH_ON, label="Устройства"),
            ft.NavigationBarDestination(icon=ft.Icons.HISTORY_OUTLINED, selected_icon=ft.Icons.HISTORY, label="История"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Настройки"),
        ],
    )

    def on_nav_change(e: ft.ControlEvent):
        state["tab"] = int(e.control.selected_index)
        build_root()

    nav.on_change = on_nav_change

    def do_logout():
        state["logged_in"] = False
        state["tab"] = 0
        build_root()

    def build_root():
        page.controls.clear()

        if not state["logged_in"]:
            page.appbar = None
            page.navigation_bar = None
            page.bgcolor = _c("#eaf1ff")
            page.add(login_view)
            page.update()
            return

        page.bgcolor = C("BG")
        page.navigation_bar = nav
        load_devices_from_api(show_error=False)
        nav.selected_index = state["tab"]

        if state["tab"] == 0:
            home_view()
        elif state["tab"] == 1:
            devices_view()
        elif state["tab"] == 2:
            history_view()
        elif state["tab"] == 3:
            settings_view()

        page.add(content)
        page.update()

    build_root()


ft.run(main)
