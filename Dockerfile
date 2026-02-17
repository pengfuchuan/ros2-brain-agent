# ROS2 Brain Agent Development Environment
# Based on ROS2 Humble

FROM ros:humble

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /ros2-brain-agent

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    ros-humble-rmw-cyclonedds-cpp \
    git \
    vim \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    pyyaml \
    pytest \
    pytest-cov

# Install ROS2 dependencies (optional Nav2 packages for real robot testing)
# Uncomment the following lines if Nav2 is needed:
# RUN apt-get update && apt-get install -y \
#     ros-humble-nav2-bringup \
#     ros-humble-nav2-msgs \
#     ros-humble-moveit-msgs \
#     && rm -rf /var/lib/apt/lists/*

# Source ROS2 environment
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc

# Set environment variables
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Default command
CMD ["bash"]
