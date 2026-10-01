"""Resource publishers on selected domains; no capture or stress generation."""
import json
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    def setup(context):
        domains=json.loads(LaunchConfiguration('domains').perform(context))
        if not isinstance(domains,list) or not domains or any(type(d) is not int or not 0<=d<=232 for d in domains):raise ValueError('Invalid resource monitor domains')
        actions=[]
        for domain in sorted(set(domains)):
            for executable in ('cpu_monitor','memory_monitor','gpu_monitor','identity_publisher'):
                actions.append(Node(package='strawberry_resource_monitor',executable=executable,
                    name=f'recording_resources_{executable}_{domain}',
                    parameters=[{'publish_rate_hz':1.0}],
                    additional_env={'ROS_DOMAIN_ID':str(domain),'STRAWBERRY_RESOURCE_MONITOR_DEV_AUTOSTART':'true'},output='log'))
        return actions
    return LaunchDescription([DeclareLaunchArgument('domains',default_value='[40,41]'),OpaqueFunction(function=setup)])
