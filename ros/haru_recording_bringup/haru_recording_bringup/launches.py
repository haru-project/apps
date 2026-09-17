"""Test orchestration outside the Recorder and Viz repositories."""
import json
import os
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def workspace():
    return Path(os.environ.get('HARU_RECORDING_WS', str(Path(get_package_share_directory('haru_recording_bringup')).parents[3])))


def description(mode):
    def setup(context):
        value=lambda name:LaunchConfiguration(name).perform(context)
        domains=json.loads(value('domains'))
        control=int(value('control_domain'))
        if not isinstance(domains,list) or not domains or any(type(d) is not int or not 0<=d<=232 for d in domains): raise ValueError('invalid domains')
        if not 0<=control<=232: raise ValueError('invalid control domain')
        root=str(Path(value('recording_root')).expanduser().resolve())
        def include(package, file, arguments):
            return IncludeLaunchDescription(PythonLaunchDescriptionSource(str(Path(get_package_share_directory(package))/'launch'/file)),launch_arguments=arguments.items())
        recorder={'domains':json.dumps(domains),'control_domain':str(control),'recording_root':root}
        actions=[SetEnvironmentVariable('ROS_DOMAIN_ID',str(control))]
        if mode=='library':
            # One worker uses the library directly; coordinator ownership stays coherent.
            domains=[control]; recorder['domains']=json.dumps(domains)
            actions.append(Node(package='haru_recorder',executable='haru_recorder',name='haru_library_recorder',parameters=[{'recording_root':root,'cloud_background_enabled':False}],output='screen'))
            actions.append(include('haru_recorder','haru_recorder.launch.py',dict(recorder,mode='coordinator')))
            actions.append(include('haru_recorder','haru_recorder.launch.py',dict(recorder,mode='monitoring')))
        elif mode in ('recorder','both','smoke'):
            actions.append(include('haru_recorder','haru_recorder.launch.py',dict(recorder,mode='combined')))
        if mode!='viz' and value('launch_resources')=='true':
            actions.append(include('haru_recording_bringup','resources.launch.py',{'domains':json.dumps(domains)}))
        if mode in ('viz','both','auto_start','library','smoke'):
            actions.append(include('haru_viz','haru_viz.launch.py',{
                'launch_recorder':'true' if mode=='auto_start' else 'false',
                'recorder_domains':json.dumps(domains),'recording_root':root,
                'launch_web_ui':value('launch_web_ui'),'web_ui_mode':'production','web_ui_host':'127.0.0.1','web_ui_port':value('web_ui_port'),
                'rosbridge_port':value('bridge_port'),'rosbridge_rgb_port':str(int(value('bridge_port'))+1),
                'rosbridge_depth_port':str(int(value('bridge_port'))+2),'rosbridge_depth_to_rgb_port':str(int(value('bridge_port'))+3),
                'discovery_enabled':'false','opus_decode_enabled':'false'}))
        if mode=='smoke':
            for domain in sorted(set(domains)):
                actions.append(Node(package='haru_recording_bringup',executable='test_publisher.py',name=f'recording_test_{domain}',additional_env={'ROS_DOMAIN_ID':str(domain)},output='screen'))
        return actions
    return LaunchDescription([
        DeclareLaunchArgument('domains',default_value='[40,41]'),
        DeclareLaunchArgument('control_domain',default_value='40'),
        DeclareLaunchArgument('recording_root',default_value=str(workspace()/'data'/('library' if mode=='library' else 'recordings'))),
        DeclareLaunchArgument('bridge_port',default_value='19291'),
        DeclareLaunchArgument('web_ui_port',default_value='15173'),
        DeclareLaunchArgument('launch_resources',default_value='true'),
        DeclareLaunchArgument('launch_web_ui',default_value='true'),
        OpaqueFunction(function=setup),
    ])
