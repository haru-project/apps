DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/speech

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Voices data
docker create --name tmp-speech ghcr.io/haru-project/haru-speech:feature-lifecycle > /dev/null
docker cp tmp-speech:/ros2_ws/src/haru-speech/configs $DATA_FOLDER/configs
docker cp tmp-speech:/ros2_ws/src/haru-speech/data/voices $DATA_FOLDER/voices
docker rm tmp-speech > /dev/null

# Give permissions
chmod -R 770 $DATA_FOLDER