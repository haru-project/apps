# Perception services
docker compose -f apps/docker-compose-perception.yaml --env-file envs/perception.env up azure-kinect-driver azure-kinect faces hands people visualization --force-recreate -d

# Speech services
docker compose -f apps/docker-compose-speech.yaml --env-file envs/speech.env up audio configure speech-recognition speaker-verification --force-recreate -d
docker compose -f apps/docker-compose-speech-lifecycle.yaml --env-file envs/speech.env up audio-start configure-start speech-recognition-start speaker-verification-start --force-recreate

# LLM services
docker compose -f apps/docker-compose-llm.yaml --env-file envs/llm.env up action-args dashboard --force-recreate -d

# Reasoner services
docker compose -f apps/docker-compose-reasoner.yaml --env-file envs/reasoner.env up bt-forest --force-recreate -d