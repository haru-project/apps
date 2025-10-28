DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/reasoner

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Reasoner tasks
docker create --name tmp-reasoner ghcr.io/haru-project/agent-reasoner:test-oct-2025
docker cp tmp-reasoner:/ros2_ws/src/agent_reasoner/haru_agent_reasoner/examples/tasks $DATA_FOLDER/tasks
docker rm tmp-reasoner

# Give permissions
sudo chmod -R a+rw $DATA_FOLDER