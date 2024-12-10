#!/bin/bash

# Exit on any error
set -e


echo "Starting installation..."

# Install system dependencies
echo "Installing system packages..."
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    python3-picamera2 \
    python3-numpy \
    python3-scipy \
    python3-libcamera \
    git \
    i2c-tools \
    libraspberrypi0 \
    python3-yaml \
    v4l-utils \
    libatlas-base-dev

# Enable required interfaces
#echo "Enabling hardware interfaces..."
#sudo raspi-config nonint do_i2c 0
#sudo raspi-config nonint do_spi 0
#sudo raspi-config nonint do_camera 0
#sudo raspi-config nonint do_rgpio 0

# Configure groups and permissions
echo "Setting up groups and permissions..."
sudo usermod -a -G gpio,i2c,video,dialout pi


# Configure L298N GPIO pins
echo "# L298N Motor Driver
gpio=4,17,27,5,6,13=op,dh" | sudo tee -a /boot/config.txt

# Install PWM support
sudo apt install -y pigpio
sudo systemctl enable pigpiod

# Set up USB permissions for LiDAR
echo "Configuring USB permissions..."
sudo tee /etc/udev/rules.d/99-lidar.rules << EOF
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE:="0666", GROUP="dialout"
EOF

# Create project directories
echo "Creating project directories..."
sudo mkdir -p /home/pi/vehicle_data/{logs,maps}
sudo chown -R pi:pi /home/pi/vehicle_data
sudo chmod -R 755 /home/pi/vehicle_data

# Set up Python virtual environment
echo "Setting up Python environment..."
cd /home/pi/vehicle_control
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt
pip install rplidar-roboticia opencv-python aiohttp numpy

# Setup systemd service
echo "Setting up system service..."
sudo cp scripts/vehicle.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/vehicle.service
sudo systemctl daemon-reload
sudo systemctl enable vehicle.service

# Basic validation
echo "Verifying installation..."
if ! [ -c "/dev/gpiochip0" ]; then
    echo "Error: GPIO not available"
    exit 1
fi

if ! [ -c "/dev/i2c-1" ]; then
    echo "Error: I2C not available"
    exit 1
fi

if ! [ -e "/dev/ttyUSB0" ]; then
    echo "Warning: LiDAR not detected. Please connect the device."
fi

echo "Installation complete!"
echo "Please reboot the system to apply all changes."

# Ask for reboot
read -p "Would you like to reboot now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo reboot
fi