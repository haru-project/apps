DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/reasoner

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Reasoner tasks
docker create --name tmp-reasoner haru/agent-reasoner:local > /dev/null
docker cp tmp-reasoner:/ros2_ws/src/agent_reasoner/haru_agent_reasoner/examples/tasks $DATA_FOLDER/tasks
docker cp tmp-reasoner:/ros2_ws/src/agent_reasoner/haru_agent_reasoner/params $DATA_FOLDER/configs
docker rm tmp-reasoner > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER