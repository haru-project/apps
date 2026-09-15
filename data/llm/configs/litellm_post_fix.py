"""LiteLLM post-call fix for bedrock-mantle Gemma 4 structured outputs.

Mantle constrained decoding sometimes emits 1-2 junk tokens AFTER the complete
JSON object (measured 2026-07-06: 5/25 default sampling, 2/25 at temp=1.0),
with finish_reason "stop". haru-llm agents strict-parse message content, so
trailing junk = ModelBehaviorError = a wedged action (no retry in haru-llm yet).
This hook trims content back to the longest valid JSON prefix ending at a
closing brace. No-op for anything that already parses or does not look like a
JSON object.

Wiring: the file must be importable by the litellm proxy (same directory as the
server config, or on PYTHONPATH) and referenced from litellm_server.yaml:
    callbacks: ["langfuse", litellm_post_fix.proxy_handler_instance]
"""
import json
from litellm.integrations.custom_logger import CustomLogger


def _trim_to_valid_json(content):
    if not content:
        return content
    s = content.strip()
    if not s.startswith("{"):
        return content
    try:
        json.loads(s)
        return content
    except Exception:
        pass
    idx = len(s)
    while True:
        idx = s.rfind("}", 0, idx)
        if idx < 0:
            return content
        cand = s[: idx + 1]
        try:
            json.loads(cand)
            return cand
        except Exception:
            continue


class MantleJsonFixHandler(CustomLogger):
    async def async_post_call_success_hook(self, data, user_api_key_dict, response):
        try:
            for choice in getattr(response, "choices", []) or []:
                msg = getattr(choice, "message", None)
                if msg is not None and isinstance(getattr(msg, "content", None), str):
                    fixed = _trim_to_valid_json(msg.content)
                    if fixed != msg.content:
                        msg.content = fixed
        except Exception:
            pass
        return response


proxy_handler_instance = MantleJsonFixHandler()
