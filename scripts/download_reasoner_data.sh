DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/reasoner

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Reasoner data
docker create --name tmp-reasoner ghcr.io/haru-project/haru-agent-reasoner:feature-migration-haru2core-v2 > /dev/null
docker cp tmp-reasoner:/opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/examples/tasks $DATA_FOLDER/tasks
docker cp tmp-reasoner:/opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/config $DATA_FOLDER/configs
docker cp tmp-reasoner:/opt/ros/jazzy/workspace/install/share/haru_agent_reasoner/params $DATA_FOLDER/configs
docker cp tmp-reasoner:/opt/ros/jazzy/workspace/install/share/behavior_tree_unity_projector/examples/resources $DATA_FOLDER/projector
docker rm tmp-reasoner > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER