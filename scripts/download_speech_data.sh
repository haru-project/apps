DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/speech

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Speech data
docker create --name tmp-speech ghcr.io/haru-project/haru-speech:ros2 > /dev/null
docker cp tmp-speech:/opt/ros/jazzy/workspace/install/share/haru_speech_ros/configs $DATA_FOLDER/configs
docker rm tmp-speech > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER