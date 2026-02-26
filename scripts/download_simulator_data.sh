DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/simulator

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Simulator data
docker create --name tmp-simulator ghcr.io/haru-project/hve-simulator:feature-ci > /dev/null
docker cp tmp-simulator:/ros2_ws/src/haru2_core/resources $DATA_FOLDER/resources
docker rm tmp-simulator > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER