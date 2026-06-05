from __future__ import annotations

import hashlib
import os
import time
from typing import Any

import httpx


DEFAULT_QIXIN_BASE_URL = "https://api.qixin.com"
DEFAULT_QIXIN_TIMEOUT_SECONDS = 15.0


class QixinConfigError(RuntimeError):
    """Raised when the Qixin integration is not configured."""


class QixinUpstreamError(RuntimeError):
    """Raised when the Qixin upstream request fails."""


class QixinClient:
    def __init__(
        self,
        *,
        app_key: str,
        secret_key: str,
        base_url: str = DEFAULT_QIXIN_BASE_URL,
        timeout_seconds: float = DEFAULT_QIXIN_TIMEOUT_SECONDS,
    ) -> None:
        self.app_key = app_key.strip()
        self.secret_key = secret_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "QixinClient":
        app_key = os.getenv("QIXIN_APP_KEY", "").strip()
        secret_key = os.getenv("QIXIN_SECRET_KEY", "").strip()
        base_url = os.getenv("QIXIN_BASE_URL", DEFAULT_QIXIN_BASE_URL).strip()
        try:
            timeout_seconds = float(
                os.getenv("QIXIN_TIMEOUT_SECONDS", str(DEFAULT_QIXIN_TIMEOUT_SECONDS))
            )
        except ValueError as exc:
            raise QixinConfigError(
                "Environment variable QIXIN_TIMEOUT_SECONDS must be a number."
            ) from exc

        if not app_key:
            raise QixinConfigError("Missing required environment variable: QIXIN_APP_KEY")
        if not secret_key:
            raise QixinConfigError("Missing required environment variable: QIXIN_SECRET_KEY")

        return cls(
            app_key=app_key,
            secret_key=secret_key,
            base_url=base_url or DEFAULT_QIXIN_BASE_URL,
            timeout_seconds=timeout_seconds,
        )

    def adv_search(self, keyword: str) -> dict[str, Any]:
        timestamp = self._timestamp_millis()
        headers = self._build_headers(timestamp)

        try:
            response = httpx.get(
                f"{self.base_url}/APIService/v2/search/advSearch",
                params={"keyword": keyword},
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise QixinUpstreamError("Qixin request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise QixinUpstreamError(
                f"Qixin returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise QixinUpstreamError(f"Qixin request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise QixinUpstreamError("Qixin returned a non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise QixinUpstreamError("Qixin returned an unexpected JSON payload.")

        return payload

    def _build_headers(self, timestamp: str) -> dict[str, str]:
        sign = hashlib.md5(f"{self.app_key}{timestamp}{self.secret_key}".encode("utf-8")).hexdigest()
        return {
            "Content-Type": "application/json",
            "charset": "utf-8",
            "Auth-Version": "2.0",
            "appkey": self.app_key,
            "timestamp": timestamp,
            "sign": sign,
        }

    @staticmethod
    def _timestamp_millis() -> str:
        return str(int(time.time() * 1000))
