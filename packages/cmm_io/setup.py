from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cmm_io'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROS2 Brain Agent Team',
    maintainer_email='maintainer@example.com',
    description='ROS2 Brain Agent - IO Layer',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'asr_client_node = cmm_io.asr_client_node:main',
            'tts_client_node = cmm_io.tts_client_node:main',
        ],
    },
)
