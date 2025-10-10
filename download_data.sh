DATA_FOLDER=./data

mkdir $DATA_FOLDER

# Download faces
docker create --name tmp-faces ghcr.io/haru-project/strawberry_ros_faces_module:latest
docker cp tmp-faces:/home/haru/.ros/strawberry_ros_faces_module $DATA_FOLDER
docker rm tmp-faces

# Give permissions
sudo chmod -R a+rw $DATA_FOLDER