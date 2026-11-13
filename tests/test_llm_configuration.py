from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load_trim_function():
    source = (ROOT / "config/llm/litellm_post_fix.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    function = next(node for node in module.body if isinstance(node, ast.FunctionDef))
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {"json": __import__("json")}
    exec(compile(isolated, "<litellm_post_fix>", "exec"), namespace)
    return namespace["trim_to_valid_json"]


def test_canonical_model_is_bedrock_mantle() -> None:
    config = yaml.safe_load((ROOT / "config/llm/litellm_server.yaml").read_text(encoding="utf-8"))
    canonical = [model for model in config["model_list"]
                 if model["model_name"] == "haru:canonical"]
    assert len(canonical) == 1
    params = canonical[0]["litellm_params"]
    assert params["model"] == "bedrock_mantle/google.gemma-4-26b-a4b"
    assert params["api_key"] == "os.environ/BEDROCK_MANTLE_API_KEY"
    assert "api_base" not in params
    assert "langfuse" not in str(config)


def test_post_fix_trims_only_trailing_json_junk() -> None:
    trim = _load_trim_function()
    assert trim('{"ok": true} trailing') == '{"ok": true}'
    assert trim('{"ok": true}') == '{"ok": true}'
    assert trim("plain text") == "plain text"
    assert trim('{"incomplete":') == '{"incomplete":'
