DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/context_manager

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Context Manager configs
docker create --name tmp-context-manager ghcr.io/haru-project/context_manager:jazzy > /dev/null
docker cp tmp-context-manager:/root/ros2_ws/src/context_manager/config $DATA_FOLDER/config
docker rm tmp-context-manager > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER
