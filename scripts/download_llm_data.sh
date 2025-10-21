DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/llm

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# LLM data
docker create --name tmp-llm ghcr.io/haru-project/haru-llm:ros2
docker cp tmp-llm:/ros2_ws/src/haru-llm/agents $DATA_FOLDER/agents
docker cp tmp-llm:/ros2_ws/src/haru-llm/logs $DATA_FOLDER/logs
docker rm tmp-llm

# Give permissions
sudo chmod -R a+rw $DATA_FOLDER