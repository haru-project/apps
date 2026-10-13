"""Check resolved Compose routing and setting precedence without starting services."""

import json
import os
from pathlib import Path
import subprocess
import unittest

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

    def config(self, stack, language=None, cli=None):
        env = {k: v for k, v in os.environ.items() if k != 'HARU_DEMO_LANGUAGE'}
        if language:
            env['HARU_DEMO_LANGUAGE'] = language
        args = [str(ROOT / 'scripts/compose.sh'), stack]
        if cli:
            args += ['--language', cli]
        args += ['--profile', 'tts', '--profile', 'ros', 'config', '--format', 'json']
        result = subprocess.run(args, env=env, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)['services']

    def test_language_and_backend_selection(self):
        for language, locale in [(None, 'en-US'), ('es', 'es-ES'), ('ja', 'ja-JP'), ('uk', 'uk-UA')]:
            with self.subTest(language=language):
                tts = self.config('tts', language)
                self.assertIn('demo_language:=' + locale, tts['ros-node']['command'])
                self.assertEqual(tts['ros-node']['environment']['HARU_DEMO_LANGUAGE'], locale)
                if language == 'uk':
                    self.assertNotIn('gpt-sovits', tts)
                    self.assertNotIn('cerevoice-api', tts)
                    self.assertNotIn('depends_on', tts['tts-client'])
                    self.assertIn('strawberry_tts.ukrainian.server', tts['tts-client']['command'])
                else:
                    self.assertIn(locale, tts['tts-client']['command'])
                    self.assertIn('gpt-sovits', tts)
                asr = self.config('speech', language)['recognition']
                self.assertIn('demo_language:=' + locale, asr['command'])
                self.assertIn('asr_model:=auto', asr['command'])

    def test_cli_precedence_and_combined_stack(self):
        services = self.config('all', 'en', cli='uk')
        self.assertIn('demo_language:=uk-UA', services['recognition']['command'])
        self.assertIn('demo_language:=uk-UA', services['ros-node']['command'])
        self.assertIn('strawberry_tts.ukrainian.server', services['tts-client']['command'])
        self.assertNotIn('gpt-sovits', services)

    def test_invalid_language_fails_before_docker(self):
        result = subprocess.run([str(ROOT/'scripts/compose.sh'), 'tts', '--language', 'xx', 'config'], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Unsupported HARU_DEMO_LANGUAGE', result.stderr)


if __name__ == '__main__':
    unittest.main()
