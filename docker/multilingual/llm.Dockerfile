FROM ghcr.io/haru-project/haru-llm@sha256:893c37cee495253ef1d0ba5fbd0cebe3a96577f9eea3a429e6ce5fedd24177fa
COPY src/haru_llm /opt/ros/jazzy/workspace/package_venv/lib/python3.12/site-packages/haru_llm
COPY src/haru_llm /opt/ros/jazzy/workspace/install/lib/python3.12/site-packages/haru_llm
COPY haru_llm_ros /opt/ros/jazzy/workspace/install/lib/python3.12/site-packages/haru_llm_ros
COPY haru_llm_ros/action_args.py /opt/ros/jazzy/workspace/install/lib/haru_llm_ros/action_args.py
COPY launch /opt/ros/jazzy/workspace/install/share/haru_llm_ros/launch
COPY configs /opt/ros/jazzy/workspace/install/share/haru_llm_ros/configs
COPY agents /opt/ros/jazzy/workspace/install/share/haru_llm_ros/agents
