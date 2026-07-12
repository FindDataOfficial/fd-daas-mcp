"""
HTTP Proxy controller for CLI-Anything harnesses.

Manages proxy settings (URL, enable/disable) and applies them before
function calls. Settings persist to a JSON config file.

Usage:
    from cli_anything.akshare.core.proxy import ProxyController

    proxy = ProxyController()
    proxy.set_proxy("http://127.0.0.1:7890")
    proxy.enable()
    proxy.apply()  # sets HTTP_PROXY, HTTPS_PROXY env vars

    # Or as context manager:
    with proxy:
        result = call_akshare_function("stock_zh_a_hist", symbol="000001")
"""
from __future__ import annotations

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Config file location: ~/.cache/cli-anything-akshare/proxy.json
_DEFAULT_CONFIG_DIR = Path.home() / ".cache" / "cli-anything-akshare"
_DEFAULT_CONFIG_PATH = _DEFAULT_CONFIG_DIR / "proxy.json"


class ProxyController:
    """Manages HTTP/HTTPS proxy for AKShare function calls.

    Reads/writes proxy config from a JSON file. When enabled, sets
    HTTP_PROXY, HTTPS_PROXY, and ALL_PROXY environment variables so
    all outbound HTTP requests go through the proxy.

    Attributes:
        config_path: Path to the proxy config JSON file.
    """

    def __init__(self, config_path: Optional[str] = None):
        self._config_path = Path(config_path or _DEFAULT_CONFIG_PATH)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        self._url: str = ""
        self._enabled: bool = False
        self._saved_env: dict[str, str] = {}
        self._load()

    # ---- properties ----

    @property
    def url(self) -> str:
        return self._url

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def status(self) -> str:
        if not self._url:
            return "No proxy configured"
        state = "ON" if self._enabled else "OFF"
        return f"Proxy [{state}]: {self._url}"

    # ---- config ----

    def set_proxy(self, url: str) -> None:
        """Set the proxy URL. Accepts http://, https://, socks5://."""
        self._url = url.strip().rstrip("/")
        self._save()

    def clear_proxy(self) -> None:
        """Remove the proxy URL and disable."""
        self.disable()
        self._url = ""
        self._save()

    def enable(self) -> None:
        """Enable the proxy. Apply environment variables."""
        self._enabled = True
        self._apply_env()
        self._save()

    def disable(self) -> None:
        """Disable the proxy. Restore original environment variables."""
        self._enabled = False
        self._restore_env()
        self._save()

    def toggle(self) -> bool:
        """Toggle proxy on/off. Returns new state."""
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    # ---- env management ----

    def apply(self) -> None:
        """Apply proxy env vars if enabled. Call before making HTTP requests."""
        if self._enabled and self._url:
            self._apply_env()

    def _apply_env(self) -> None:
        """Set HTTP_PROXY, HTTPS_PROXY, ALL_PROXY env vars."""
        if not self._url:
            return
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            self._saved_env[key] = os.environ.get(key, "")
            os.environ[key] = self._url
        os.environ["ALL_PROXY"] = self._url
        logger.info("Proxy applied: %s", self._url)

    def _restore_env(self) -> None:
        """Restore original proxy env vars."""
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            if key in self._saved_env:
                if self._saved_env[key]:
                    os.environ[key] = self._saved_env[key]
                else:
                    os.environ.pop(key, None)
        os.environ.pop("ALL_PROXY", None)
        self._saved_env.clear()
        logger.info("Proxy disabled, env restored")

    # ---- persistence ----

    def _save(self) -> None:
        """Save current config to JSON file."""
        data = {"url": self._url, "enabled": self._enabled}
        with open(self._config_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        """Load config from JSON file if it exists."""
        if self._config_path.exists():
            try:
                with open(self._config_path) as f:
                    data = json.load(f)
                self._url = data.get("url", "")
                self._enabled = data.get("enabled", False)
                if self._enabled and self._url:
                    self._apply_env()
            except (json.JSONDecodeError, KeyError):
                pass

    # ---- context manager ----

    def __enter__(self):
        """Context manager: enable proxy, restore on exit."""
        self._was_enabled = self._enabled
        if not self._enabled:
            self.enable()
        return self

    def __exit__(self, *args):
        if not self._was_enabled:
            self.disable()
        return False


# Module-level singleton
_proxy_controller: Optional[ProxyController] = None


def get_proxy(config_path: Optional[str] = None) -> ProxyController:
    """Get or create the singleton ProxyController."""
    global _proxy_controller
    if _proxy_controller is None:
        _proxy_controller = ProxyController(config_path)
    return _proxy_controller
