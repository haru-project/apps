from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_start_submits_selected_demo_and_uses_backend_dependencies(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (tmp_path / 'envs').mkdir()
    (tmp_path / 'envs/demo.env').write_text('HARU_DEMO_LANGUAGE=uk\n')
    for filename in ('start.sh', 'run.sh'):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    shutil.copy2(ROOT / 'scripts/demo_language.sh', scripts / 'demo_language.sh')
    (scripts / 'setup_multilingual.sh').write_text('#!/bin/bash\nexit 0\n')
    (scripts / 'compose.sh').write_text('''#!/bin/bash
[[ "$2" == ps ]] && exit 0
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/demo_language.sh"
printf '%s %s\\n' "$HARU_DEMO_LANGUAGE" "$*" >> "$ROOT_DIR/calls"
''')
    env = {k: v for k, v in os.environ.items() if k != 'HARU_DEMO_LANGUAGE'}
    env['DISPLAY'] = 'invalid'
    subprocess.run(['bash', str(tmp_path / 'start.sh')], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    calls = (tmp_path / 'calls').read_text().splitlines()
    assert all(call.startswith('uk-UA ') for call in calls)
    tts = next(call for call in calls if 'tts --profile' in call)
    assert 'tts-client ros-node' in tts
    assert 'gpt-sovits' not in tts and 'cerevoice-api' not in tts
    assert any('reasoner --profile scenario up execute-task-scenario' in call for call in calls)
    assert any('user up episode-builder' in call for call in calls)


def test_localized_scenarios_have_native_goals_and_no_scripted_english():
    import json
    for locale in ('en-US', 'es-ES', 'ja-JP', 'uk-UA'):
        scenario = json.loads((ROOT / f'config/demo/MultilingualDemo_{locale}.json').read_text())
        assert scenario['demo_language'] == locale
        goal = json.loads(scenario['actions'][0]['action_goal'])
        assert goal['description']
        assert goal['additional_instructions']
        assert scenario['actions'][0]['action_content'] == []


def test_proxy_auth_is_private_idempotent_and_keeps_provider_credentials(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location('configure_llm_auth', ROOT / 'scripts/configure_llm_auth.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / 'llm.secrets.env'
    path.write_text('# provider\nBEDROCK_MANTLE_API_KEY=provider-secret\nLLM_SERVER_API_KEY=\n')
    module.configure(path)
    text = path.read_text()
    values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    assert values['BEDROCK_MANTLE_API_KEY'] == 'provider-secret'
    assert values['LITELLM_MASTER_KEY'] == values['LLM_SERVER_API_KEY']
    assert values['LLM_SERVER_API_KEY'].startswith('sk-')
    assert path.stat().st_mode & 0o777 == 0o600
    module.configure(path)
    assert path.read_text() == text


def test_user_supplied_proxy_master_key_is_preserved(tmp_path):
    path = tmp_path / 'llm.secrets.env'
    key = 'sk-' + 'a' * 64
    path.write_text(f'LITELLM_MASTER_KEY={key}\nLLM_SERVER_API_KEY=old-client-key\n')
    subprocess.run(['python3', str(ROOT / 'scripts/configure_llm_auth.py'), str(path)], check=True)
    assert f'LITELLM_MASTER_KEY={key}' in path.read_text()
    assert f'LLM_SERVER_API_KEY={key}' in path.read_text()


def test_cerevoice_language_tracks_selected_demo(tmp_path):
    (tmp_path / 'envs').mkdir()
    (tmp_path / 'envs/demo.env').write_text('HARU_DEMO_LANGUAGE=en-US\n')
    for language, expected in [('es', 'es-ES'), ('en', 'en-US'), ('ja', 'en-US')]:
        env = dict(os.environ, HARU_DEMO_LANGUAGE=language, ROOT_DIR=str(tmp_path))
        command = f'source "{ROOT / "scripts/demo_language.sh"}"; echo "$HARU_CEREVOICE_LANGUAGE"'
        result = subprocess.run(['bash', '-c', command], env=env, check=True, capture_output=True, text=True)
        assert result.stdout.strip() == expected
