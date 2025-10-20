DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/speech

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# LLM data
docker create --name tmp-speech ghcr.io/haru-project/haru-speech:ros2-fastdds
docker cp tmp-speech:/ros2_ws/src/haru-speech/data/voices $DATA_FOLDER/voices
docker rm tmp-speech

# Give permissions
sudo chmod -R a+rw $DATA_FOLDER