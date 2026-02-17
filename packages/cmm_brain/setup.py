from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cmm_brain'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROS2 Brain Agent Team',
    maintainer_email='maintainer@example.com',
    description='ROS2 Brain Agent - Brain Layer',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'dialog_manager_node = cmm_brain.dialog_manager_node:main',
            'llm_orchestrator_node = cmm_brain.llm_orchestrator_node:main',
            'tool_router_node = cmm_brain.tool_router_node:main',
            'memory_node = cmm_brain.memory_node:main',
        ],
    },
)
