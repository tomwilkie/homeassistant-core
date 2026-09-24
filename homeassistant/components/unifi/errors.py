"""Errors for the UniFi Network integration."""

import aiounifi

from homeassistant.exceptions import HomeAssistantError


def _controller_error_msg(err: aiounifi.AiounifiException) -> str | None:
    """Return the message code the controller rejected a request with."""
    payload = err.args[0] if err.args else None
    if not isinstance(payload, dict) or not isinstance(
        meta := payload.get("meta"), dict
    ):
        return None
    msg = meta.get("msg")
    return msg if isinstance(msg, str) else None


def is_controller_error(err: aiounifi.AiounifiException, msg: str) -> bool:
    """Check if the controller rejected a request with a specific message code."""
    return _controller_error_msg(err) == msg


def controller_error_reason(err: aiounifi.AiounifiException) -> str:
    """Return a short reason for a failed request, never the raw payload."""
    if (msg := _controller_error_msg(err)) is not None:
        return msg
    if err.args and isinstance(err.args[0], str):
        return err.args[0]
    return type(err).__name__


class UnifiException(HomeAssistantError):
    """Base class for UniFi Network exceptions."""


class AlreadyConfigured(UnifiException):
    """Controller is already configured."""


class AuthenticationRequired(UnifiException):
    """Unknown error occurred."""


class CannotConnect(UnifiException):
    """Unable to connect to UniFi Network."""


class LoginRequired(UnifiException):
    """Integration got logged out."""


class UserLevel(UnifiException):
    """User level too low."""
