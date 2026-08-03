"""Normalize Bedrock Mantle Gemma structured responses."""

import json

from litellm.integrations.custom_logger import CustomLogger


def trim_to_valid_json(content: str | None) -> str | None:
    """Trim junk after a complete JSON object while leaving other text untouched."""
    if not content:
        return content
    stripped = content.strip()
    if not stripped.startswith("{"):
        return content
    try:
        json.loads(stripped)
        return content
    except json.JSONDecodeError:
        pass

    index = len(stripped)
    while True:
        index = stripped.rfind("}", 0, index)
        if index < 0:
            return content
        candidate = stripped[: index + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue


class MantleJsonFixHandler(CustomLogger):
    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        try:
            for choice in getattr(response, "choices", []) or []:
                message = getattr(choice, "message", None)
                if message is not None and isinstance(getattr(message, "content", None), str):
                    message.content = trim_to_valid_json(message.content)
        except Exception:
            # A diagnostics hook must never turn a successful model call into a failure.
            pass
        return response


proxy_handler_instance = MantleJsonFixHandler()
