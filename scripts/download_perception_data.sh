DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_FOLDER=$DIR/../data/perception

rm -rf $DATA_FOLDER
mkdir -p $DATA_FOLDER

# Kinect rules
wget -O "99-k4a.rules" "https://robotics.upo.es/~nbousan/azure_kinect_libraries/99-k4a.rules"
sudo mv 99-k4a.rules /etc/udev/rules.d/99-k4a.rules && sudo chmod 777 /etc/udev/rules.d/99-k4a.rules

# Give permissions
sudo chmod -R a+rw $DATA_FOLDER