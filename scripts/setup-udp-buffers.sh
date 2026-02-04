#!/bin/bash
# Setup UDP buffer sizes for ROS2 high-bandwidth message transport
# Run this once on system setup or before starting docker-compose services

set -e

echo "Configuring kernel UDP buffer sizes for ROS2..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Set runtime values
sysctl -w net.core.rmem_max=134217728
sysctl -w net.core.wmem_max=134217728
sysctl -w net.core.rmem_default=134217728
sysctl -w net.core.wmem_default=134217728

# Make persistent across reboots
SYSCTL_FILE="/etc/sysctl.d/99-ros2-udp.conf"
cat > "$SYSCTL_FILE" <<EOF
# Increase UDP buffer sizes for ROS2 large message transport
# Created by setup-udp-buffers.sh
net.core.rmem_max=134217728
net.core.wmem_max=134217728
net.core.rmem_default=134217728
net.core.wmem_default=134217728
EOF

echo "✓ UDP buffer sizes configured"
echo "✓ Configuration saved to $SYSCTL_FILE (persists across reboots)"
