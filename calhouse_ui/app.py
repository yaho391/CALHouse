from __future__ import annotations

import inspect

import flet as ft

from .legacy_app import main as legacy_main


class CalHouseApp:
    """Thin application wrapper used while the legacy Flet screen is split up."""

    def __init__(self, page: ft.Page):
        self.page = page

    async def run(self):
        result = legacy_main(self.page)
        if inspect.isawaitable(result):
            await result


async def main(page: ft.Page):
    await CalHouseApp(page).run()
