# Perception system (HCA)
echo Starting perception system...
docker compose -f apps/docker-compose-perception.yaml --env-file envs/perception.env up azure-kinect-driver azure-kinect faces hands people visualization --force-recreate -d
sleep 5

# Speech layer
echo Launching speech layer nodes...
docker compose -f apps/docker-compose-speech.yaml --env-file envs/speech.env up audio configure speech-recognition speaker-verification --force-recreate -d
sleep 10
echo Starting speech layer nodes...
docker compose -f apps/docker-compose-speech-lifecycle.yaml --env-file envs/speech.env up audio-start configure-start speech-recognition-start speaker-verification-start --force-recreate
sleep 5

# LLM layer
echo Launching LLM layer nodes...
docker compose -f apps/docker-compose-llm.yaml --env-file envs/llm.env up action-args dashboard server webui --force-recreate -d
sleep 10
echo Starting LLM layer nodes...
docker compose -f apps/docker-compose-llm-lifecycle.yaml --env-file envs/llm.env up action-args-start dashboard-start --force-recreate
sleep 5


# Agent reasoner
echo Launching Agent reasoner...
docker compose -f apps/docker-compose-reasoner.yaml --env-file envs/reasoner.env up bt-forest reasoner --force-recreate -d
sleep 5

# DEMO
echo Launching TESTr
docker compose -f apps/docker-compose-reasoner.yaml --env-file envs/reasoner.env up context-manager execute-task-test
