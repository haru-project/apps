FROM ghcr.io/haru-project/haru-speech-recognition@sha256:74e9a5ee224538def5df7e15f9784374d6c65e143acfd5ab0b59ab128f714100
COPY src/haru_speech /opt/ros/jazzy/workspace/install/lib/python3.12/site-packages/haru_speech
COPY src/haru_speech/nodes/speech_to_text.py /opt/ros/jazzy/workspace/install/lib/haru_speech/speech_to_text.py
COPY launch /opt/ros/jazzy/workspace/install/share/haru_speech/launch
COPY configs /opt/ros/jazzy/workspace/install/share/haru_speech/configs
