docker compose -f apps/docker-compose-perception.yaml --env-file envs/perception.env down
docker compose -f apps/docker-compose-speech.yaml --env-file envs/speech.env down
docker compose -f apps/docker-compose-llm.yaml --env-file envs/llm.env down
docker compose -f apps/docker-compose-reasoner.yaml --env-file envs/reasoner.env down
docker compose -f apps/docker-compose-tts.yaml --env-file envs/tts.env down

docker system prune -f