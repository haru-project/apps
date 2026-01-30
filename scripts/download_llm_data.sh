DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/llm

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# LLM agents and logs
docker create --name tmp-llm haru/haru-llm:local > /dev/null
docker cp tmp-llm:/ros2_ws/src/haru-llm/agents $DATA_FOLDER/agents
docker cp tmp-llm:/ros2_ws/src/haru-llm/configs $DATA_FOLDER/configs
docker rm tmp-llm > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER