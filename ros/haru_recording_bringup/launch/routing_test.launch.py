"""Isolated synthetic routing stack. It never starts a recording automatically."""
import json
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument,OpaqueFunction,IncludeLaunchDescription,SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def setup(context):
    source=int(LaunchConfiguration('source_domain').perform(context));target=int(LaunchConfiguration('robot_domain').perform(context))
    if not 0<=source<=232 or not 0<=target<=232 or source==target or source in (19,200) or target in (19,200):raise ValueError('Synthetic tests require distinct domains other than 19/200')
    root=Path(LaunchConfiguration('recording_root').perform(context)).expanduser();root.mkdir(parents=True,exist_ok=True)
    config=root/'synthetic-bridge.yaml'
    config.write_text(f'name: synthetic_bridge\nfrom_domain: {source}\nto_domain: {target}\ntopics:\n  /tf:\n    type: tf2_msgs/msg/TFMessage\n  /tf_static:\n    type: tf2_msgs/msg/TFMessage\n  /shared:\n    type: std_msgs/msg/String\n')
    recorder=Path(get_package_share_directory('haru_recorder'))/'launch/haru_recorder.launch.py'
    viz=Path(get_package_share_directory('haru_viz'))/'launch/haru_viz.launch.py'
    return [
      SetEnvironmentVariable("ROS_DOMAIN_ID",str(target)),
      Node(package='domain_bridge',executable='domain_bridge',arguments=[str(config)],output='screen'),
      IncludeLaunchDescription(PythonLaunchDescriptionSource(str(recorder)),launch_arguments={'mode':'worker','domains':json.dumps([source,target]),'recording_root':str(root)}.items()),
      Node(package='haru_recorder',executable='haru_recorder_coordinator',additional_env={'ROS_DOMAIN_ID':str(target)},parameters=[{'recording_root':str(root),'domains':[source,target],'discovery_domains':[source,target]}],output='screen'),
      *[Node(package='haru_recording_bringup',executable='routing_test_publisher.py',arguments=['--role',role],additional_env={'ROS_DOMAIN_ID':str(domain)},output='screen') for domain,role in ((source,'source'),(target,'robot'))],
      IncludeLaunchDescription(PythonLaunchDescriptionSource(str(viz)),launch_arguments={'rosbridge_port':'19391','rosbridge_rgb_port':'19392','rosbridge_depth_port':'19393','rosbridge_depth_to_rgb_port':'19394','web_ui_port':'15183','web_ui_mode':'production','launch_web_ui':'true','web_ui_host':'127.0.0.1','launch_recorder':'false','discovery_enabled':'false','opus_decode_enabled':'false'}.items()),
    ]


def generate_launch_description():
    return LaunchDescription([
      DeclareLaunchArgument('source_domain',default_value='93'),DeclareLaunchArgument('robot_domain',default_value='94'),
      DeclareLaunchArgument('recording_root',default_value=str(Path.home()/'haru_recording_ws/data/routing-test')),
      OpaqueFunction(function=setup)])
