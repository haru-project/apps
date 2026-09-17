#!/usr/bin/env python3
"""Synthetic demo inputs; contains no recording calls."""
import argparse
import rclpy
from rclpy.qos import QoSProfile,DurabilityPolicy
from std_msgs.msg import String
from geometry_msgs.msg import TransformStamped
from tf2_msgs.msg import TFMessage
from sensor_msgs.msg import Image,CompressedImage

def main():
    args=argparse.ArgumentParser();args.add_argument('--role',choices=['source','robot'],required=True);options,ros=args.parse_known_args()
    rclpy.init(args=ros);node=rclpy.create_node('synthetic_'+options.role)
    shared=node.create_publisher(String,'/shared',100)
    transforms=node.create_publisher(TFMessage,'/tf',100)
    static=node.create_publisher(TFMessage,'/tf_static',QoSProfile(depth=100,durability=DurabilityPolicy.TRANSIENT_LOCAL))
    app=node.create_publisher(String,'/haru_llm/state',10) if options.role=='robot' else None
    raw=node.create_publisher(Image,'/perception/sensor/camera/image_raw',10) if options.role=='source' else None
    compressed=node.create_publisher(CompressedImage,'/perception/sensor/camera/compressed',10) if raw else None
    sequence=0
    def publish():
        nonlocal sequence
        shared.publish(String(data=f'{options.role}:{sequence}'))
        tf=TransformStamped();tf.header.frame_id='world';tf.child_frame_id=f'{options.role}-{sequence}';tf.transform.rotation.w=1.;tf.header.stamp=node.get_clock().now().to_msg()
        transforms.publish(TFMessage(transforms=[tf]))
        if sequence==0:static.publish(TFMessage(transforms=[tf]))
        if app:app.publish(String(data=f'llm:{sequence}'))
        if raw:
            raw.publish(Image(height=1,width=1,encoding='mono8',step=1,data=[sequence%255]))
            compressed.publish(CompressedImage(format='synthetic/test',data=[sequence%255]))
        sequence+=1
    node.create_timer(.1,publish)
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:node.destroy_node();rclpy.try_shutdown()
if __name__=='__main__':main()
