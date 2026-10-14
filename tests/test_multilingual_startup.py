from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_start_submits_selected_demo_and_uses_backend_dependencies(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    (tmp_path / 'envs').mkdir()
    (tmp_path / 'envs/all.env').write_text('HARU_DEMO_LANGUAGE=uk\n')
    for filename in ('start.sh', 'run.sh'):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    stale = tmp_path / 'stale-authority'
    stale.mkdir()
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    authority = runtime / '.mutter-Xwaylandauth.test'
    authority.write_text('test cookie')
    start = tmp_path / 'start.sh'
    start.write_text(start.read_text().replace('/run/user/1000/gdm/Xauthority', str(stale)))
    shutil.copy2(ROOT / 'scripts/demo_language.sh', scripts / 'demo_language.sh')
    (scripts / 'compose.sh').write_text('''#!/bin/bash
[[ "$2" == ps ]] && exit 0
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT_DIR/scripts/demo_language.sh"
printf '%s %s\\n' "$HARU_DEMO_LANGUAGE" "$*" >> "$ROOT_DIR/calls"
printf '%s\\n' "$XAUTHORITY" >> "$ROOT_DIR/authorities"
''')
    env = {k: v for k, v in os.environ.items() if k != 'HARU_DEMO_LANGUAGE'}
    env.pop('XAUTHORITY', None)
    env['DISPLAY'] = 'invalid'
    env['XDG_RUNTIME_DIR'] = str(runtime)
    subprocess.run(['bash', str(tmp_path / 'start.sh')], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    calls = (tmp_path / 'calls').read_text().splitlines()
    assert all(call.startswith('uk-UA ') for call in calls)
    assert set((tmp_path / 'authorities').read_text().splitlines()) == {str(authority)}
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


def test_cerevoice_language_tracks_selected_demo(tmp_path):
    (tmp_path / 'envs').mkdir()
    (tmp_path / 'envs/all.env').write_text('HARU_DEMO_LANGUAGE=en-US\n')
    for language, expected in [('es', 'es-ES'), ('en', 'en-US'), ('ja', 'en-US')]:
        env = dict(os.environ, HARU_DEMO_LANGUAGE=language, ROOT_DIR=str(tmp_path))
        command = f'source "{ROOT / "scripts/demo_language.sh"}"; echo "$HARU_CEREVOICE_LANGUAGE"'
        result = subprocess.run(['bash', '-c', command], env=env, check=True, capture_output=True, text=True)
        assert result.stdout.strip() == expected


def test_localized_demo_preserves_food_tv_flow_and_goal_contract():
    import json
    import re

    def load(locale):
        return json.loads((ROOT / f'config/demo/MultilingualDemo_{locale}.json').read_text())

    def contract(value, key=None):
        if isinstance(value, dict):
            return {k: contract(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [contract(v, key) for v in value]
        if key == 'action_goal' and value:
            return contract(json.loads(value))
        if isinstance(value, str) and key in {'description', 'additional_instructions', 'metainfo'}:
            return re.findall(r'\{[a-z_]+\}', value)
        return value

    english = load('en-US')
    goals = [json.loads(a['action_goal']) for a in english['actions'] if a.get('action_goal')]
    assert [g['id'] for g in goals] == [
        'greet', 'ask_about_food', 'haru_share_ice_cream',
        'ask_about_favorite_movie_or_tv_show', 'haru_share_star_wars', 'closing',
    ]
    assert len(english['actions']) == 14
    assert all(a.get('action_content') == [] for a in english['actions'] if a.get('action_goal'))
    assert [r['routine'] for r in english['actions'][-1]['action_content'][0]['value']] == [2046, 2045]
    assert 'chocolate mint' in goals[2]['description']
    assert 'Star Wars' in goals[4]['description']
    for locale in ('es-ES', 'ja-JP', 'uk-UA'):
        localized = load(locale)
        localized['demo_language'] = 'en-US'
        # Text varies; dependencies, criteria, placeholder counts/order and timeouts must not.
        assert contract(localized) == contract(english)
        for a, b in zip(localized['actions'], english['actions'], strict=True):
            if a.get('action_goal'):
                g, reference = json.loads(a['action_goal']), json.loads(b['action_goal'])
                assert g['description'] != reference['description']
                assert g['additional_instructions'][-1] != reference['additional_instructions'][-1]
