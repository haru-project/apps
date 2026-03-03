DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/llm

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# LLM data
docker create --name tmp-llm ghcr.io/haru-project/haru-llm:feature-ci > /dev/null
docker cp tmp-llm:/opt/ros/jazzy/workspace/install/share/haru_llm_ros/configs $DATA_FOLDER/configs
docker cp tmp-llm:/opt/ros/jazzy/workspace/install/share/haru_llm_ros/agents $DATA_FOLDER/agents
docker rm tmp-llm > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER