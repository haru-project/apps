DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/tts

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Voices data
docker create --name tmp-tts ghcr.io/haru-project/strawberry-tts:ros2 > /dev/null
docker cp tmp-tts:/ros2_ws/src/strawberry_tts/configs $DATA_FOLDER/configs
docker cp tmp-tts:/ros2_ws/src/strawberry_tts/ref_audio $DATA_FOLDER/ref_audio

docker rm tmp-tts > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER
