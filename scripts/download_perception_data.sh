DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/perception

mkdir -p $DATA_FOLDER

# Faces data
docker create --name tmp-faces ghcr.io/haru-project/strawberry_ros_faces_module:latest
docker cp tmp-faces:/home/haru/.ros/strawberry_ros_faces_module $DATA_FOLDER
docker rm tmp-faces

# Give permissions
sudo chmod -R a+rw $DATA_FOLDER