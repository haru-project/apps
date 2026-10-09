import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class StartupNetworkOrderTest(unittest.TestCase):
    def test_networks_precede_ros_and_failure_stops_startup(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                shutil.copyfile(Path(__file__).parents[1] / "start.sh", root / "start.sh")
                (root / "scripts").mkdir()
                (root / "scripts/compose.sh").write_text(
                    'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
                    'if [[ "${FAIL_REDIS:-}" == 1 && "$*" == "llm up redis --force-recreate -d" ]]; then exit 42; fi\n'
                )
                (root / "xhost").write_text("#!/bin/sh\nexit 0\n")
                (root / "xhost").chmod(0o755)
                env = dict(os.environ, CALL_LOG=str(root / "calls"), DISPLAY=":test",
                           XAUTHORITY=str(root / "xauth"), FAIL_REDIS="1" if fail else "0",
                           PATH=str(root) + os.pathsep + os.environ["PATH"])
                result = subprocess.run(["bash", "start.sh"], cwd=root, env=env)
                calls = (root / "calls").read_text().splitlines()
                up = [call for call in calls if " up " in call]
                self.assertEqual(up[:2], ["simulator up web-server --force-recreate -d", "llm up redis --force-recreate -d"])
                if fail:
                    self.assertEqual(result.returncode, 42)
                    self.assertEqual(len(up), 2)
                else:
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(up[2], "ipad up server --force-recreate -d")
                    self.assertNotIn("simulator up unity-app web-server --force-recreate -d", calls)


if __name__ == "__main__":
    unittest.main()
