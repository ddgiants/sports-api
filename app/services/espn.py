from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx


class ESPNClientError(RuntimeError):
    def __init__(self, url: str, message: str, status_code: int | None = None) -> None:
        super().__init__(f"{message}: {url}")
        self.url = url
        self.status_code = status_code


class ESPNClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        max_retries: int,
        user_agent: str,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": user_agent,
            },
        )
        self._max_retries = max_retries

    async def __aenter__(self) -> ESPNClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> tuple[dict[str, Any], str]:
        url = str(self._client.base_url.join(path))
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt >= self._max_retries:
                    raise ESPNClientError(url, f"ESPN request failed: {exc}") from exc
                await asyncio.sleep(min(2**attempt, 8))
                continue

            if response.is_success:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ESPNClientError(url, "ESPN returned invalid JSON") from exc
                if not isinstance(payload, dict):
                    raise ESPNClientError(url, "ESPN returned a non-object JSON payload")
                return payload, str(response.url)

            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self._max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = min(2**attempt, 8)
                if retry_after and retry_after.isdigit():
                    delay = min(int(retry_after), 30)
                await asyncio.sleep(delay)
                continue

            detail = response.text[:300].strip()
            raise ESPNClientError(
                str(response.url),
                f"ESPN returned HTTP {response.status_code}: {detail}",
                response.status_code,
            )

        raise AssertionError("unreachable")
