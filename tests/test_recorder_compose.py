"""Run with python3 -m unittest discover -s tests -p test_recorder_compose.py."""
import json
import os
from pathlib import Path
import subprocess
import unittest

class RecorderCompose(unittest.TestCase):
    def test_domain_wiring(self):
        root=Path(__file__).resolve().parents[1]
        for domain in ('0','19'):
            with self.subTest(domain=domain):
                env=dict(os.environ,HARU_ROBOT_ROS_DOMAIN_ID=domain,HARU_PERCEPTION_ROS_DOMAIN_ID='200',HARU_RECORDER_CONTROL_DOMAIN='200')
                config=json.loads(subprocess.check_output(['docker','compose','-f','apps/docker-compose-recorder.yaml','--env-file','envs/recorder.env','config','--format','json'],cwd=root,env=env,text=True))
                service=config['services']['recorder'];settings=service['environment']
                self.assertEqual(json.loads(settings['HARU_RECORDER_DOMAINS']),[int(domain),200])
                self.assertEqual(settings['HARU_ROBOT_ROS_DOMAIN_ID'],domain)
                self.assertEqual(settings['ROS_DOMAIN_ID'],'200')
                self.assertEqual(service['network_mode'],'host')
