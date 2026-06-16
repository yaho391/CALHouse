# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

import httpx


class ApiClientTimeoutError(TimeoutError):
    """Raised when the CALHouse API or an integration endpoint does not answer in time."""


class ApiClientRequestError(ConnectionError):
    """Raised when the CALHouse API cannot be reached."""


class CalHouseApiClient:
    """Small reusable HTTP client for the Flet UI."""

    def __init__(self, base_url: str, timeout: float, token_getter: Callable[[], str | None] | None = None):
        self.timeout = timeout
        self._token_getter = token_getter or (lambda: None)
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    async def aclose(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()

    def auth_headers(self) -> dict[str, str]:
        token = self._token_getter()
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    async def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.request(
                method=method.upper(),
                url=path,
                json=payload,
                headers=self.auth_headers(),
                timeout=self.timeout if timeout is None else timeout,
            )
        except httpx.TimeoutException as ex:
            raise ApiClientTimeoutError() from ex
        except httpx.RequestError as ex:
            raise ApiClientRequestError(str(ex)) from ex
