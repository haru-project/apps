#!/usr/bin/env python3
import json
import os
import rclpy
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import String
rclpy.init()
node=rclpy.create_node('recording_test_publisher')
pub=node.create_publisher(String,'/haru_recording_test/chatter',10)
sequence=0
def publish():
    global sequence
    pub.publish(String(data=json.dumps({'domain':int(os.environ.get('ROS_DOMAIN_ID','0')),'sequence':sequence})))
    sequence+=1
node.create_timer(.1,publish)
try:rclpy.spin(node)
except (KeyboardInterrupt,ExternalShutdownException):pass
finally:
    node.destroy_node()
    if rclpy.ok():rclpy.shutdown()
