"""Check resolved Compose routing and setting precedence without starting services."""

import json
import os
from pathlib import Path
import subprocess
import unittest
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[1]


class MultilingualComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.placeholder = ROOT / 'envs/llm.secrets.env'
        cls.created = not cls.placeholder.exists()
        if cls.created:
            cls.placeholder.write_text('# Empty credentials for config-only tests.\n')

    @classmethod
    def tearDownClass(cls):
        if cls.created:
            cls.placeholder.unlink()

    def config(self, stack, language=None, cli=None, root=ROOT):
        env = {k: v for k, v in os.environ.items() if k != 'HARU_DEMO_LANGUAGE'}
        if language:
            env['HARU_DEMO_LANGUAGE'] = language
        args = [str(root / 'scripts/compose.sh'), stack]
        if cli:
            args += ['--language', cli]
        args += ['--profile', 'tts', '--profile', 'ros', 'config', '--format', 'json']
        result = subprocess.run(args, env=env, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['services']

    def test_language_and_backend_selection(self):
        for language, locale in [('en', 'en-US'), ('es', 'es-ES'), ('ja', 'ja-JP'), ('uk', 'uk-UA')]:
            with self.subTest(language=language):
                tts = self.config('tts', language)
                self.assertIn('default_language_code:=' + locale, tts['ros-node']['command'])
                self.assertEqual(tts['ros-node']['environment']['HARU_DEMO_LANGUAGE'], locale)
                if language == 'uk':
                    self.assertNotIn('gpt-sovits', tts)
                    self.assertNotIn('cerevoice-api', tts)
                    self.assertTrue(all(not dependency['required'] for dependency in tts['tts-client']['depends_on'].values()))
                    self.assertEqual(tts['tts-client']['command'][0], '/usr/local/bin/start-tts')
                else:
                    self.assertIn(locale, tts['tts-client']['command'])
                    self.assertIn('gpt-sovits', tts)
                asr = self.config('speech', language)['recognition']
                self.assertEqual(asr['image'], 'ghcr.io/haru-project/haru-speech-recognition:feature-multilingual')
                self.assertEqual(asr['environment']['HARU_PARAM__DEMO_LANGUAGE'], locale)
                self.assertEqual(asr['environment']['HARU_PARAM__ASR_MODEL'], 'auto')

    def test_cli_precedence_and_combined_stack(self):
        services = self.config('all', 'en', cli='uk')
        self.assertEqual(services['recognition']['environment']['HARU_PARAM__DEMO_LANGUAGE'], 'uk-UA')
        self.assertIn('default_language_code:=uk-UA', services['ros-node']['command'])
        self.assertEqual(services['tts-client']['command'][0], '/usr/local/bin/start-tts')
        self.assertNotIn('gpt-sovits', services)
        mounts = {v['target']: v for v in services['reasoner']['volumes']}
        self.assertIn('/demo', mounts)
        self.assertTrue(mounts['/demo']['read_only'])
        self.assertEqual(Path(mounts['/demo']['source']), ROOT / 'config/demo')
        for name in ('action-args', 'reasoner'):
            self.assertIn('demo_language:=uk-UA', services[name]['command'])
        for name in ('action-args', 'reasoner', 'bt-forest'):
            self.assertEqual(services[name]['environment']['HARU_DEMO_LANGUAGE'], 'uk-UA')

        builder = self.config('user', 'uk')['episode-builder']
        self.assertEqual(builder['environment']['HARU_DEMO_LANGUAGE'], 'uk-UA')

    def test_remaining_stacks_can_select_english(self):
        for stack, service in (("llm", "action-args"), ("reasoner", "reasoner"), ("user", "episode-builder")):
            self.assertEqual(self.config(stack, "en")[service]["environment"]["HARU_DEMO_LANGUAGE"], "en-US")

    def test_single_file_selects_entire_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'apps', root / 'apps')
            shutil.copytree(ROOT / 'envs', root / 'envs', ignore=shutil.ignore_patterns('*.secrets.env'))
            (root / 'scripts').mkdir()
            for filename in ('compose.sh', 'demo_language.sh'):
                shutil.copy2(ROOT / 'scripts' / filename, root / 'scripts' / filename)
            (root / 'envs/all.env').write_text('HARU_DEMO_LANGUAGE=es')
            for stack, service in (('speech', 'recognition'), ('tts', 'tts-client'), ('llm', 'action-args'), ('reasoner', 'reasoner'), ('user', 'episode-builder')):
                self.assertEqual(self.config(stack, root=root)[service]['environment']['HARU_DEMO_LANGUAGE'], 'es-ES')
            result = subprocess.run([str(root / 'scripts/compose.sh'), 'reasoner', '--profile', 'scenario', 'config', '--format', 'json'], capture_output=True, text=True, check=True)
            scenario = json.loads(result.stdout)['services']['execute-task-scenario']
            self.assertTrue(any('/demo/MultilingualDemo_es-ES.json' in arg for arg in scenario['command']))
            # The default remains English when the setting is absent.
            (root / 'envs/all.env').write_text('')
            for stack, service in (('llm', 'action-args'), ('reasoner', 'reasoner'), ('user', 'episode-builder')):
                self.assertEqual(self.config(stack, root=root)[service]['environment']['HARU_DEMO_LANGUAGE'], 'en-US')

    def test_invalid_language_fails_before_docker(self):
        result = subprocess.run([str(ROOT/'scripts/compose.sh'), 'tts', '--language', 'xx', 'config'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Unsupported HARU_DEMO_LANGUAGE', result.stderr)


if __name__ == '__main__':
    unittest.main()
