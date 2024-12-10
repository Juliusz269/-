
import os
from dataclasses import dataclass

@dataclass
class HardwareConfig: 
    
    LEFT_MOTOR_FWD = 17
    LEFT_MOTOR_BWD = 27
    LEFT_MOTOR_EN = 4
    RIGHT_MOTOR_FWD = 5
    RIGHT_MOTOR_BWD = 6
    RIGHT_MOTOR_EN  = 13
    
    # Hardware settings
    LIDAR_PORT: str = '/dev/ttyUSB0'
    LIDAR_BAUDRATE: int = 115200
    CAMERA_RESOLUTION: tuple = (640, 480)
    CAMERA_FRAMERATE: int = 30

@dataclass
class ExplorerConfig:
    MAP_SIZE: int = 1000
    RESOLUTION: float = 0.05
    MIN_DISTANCE: float = 0.3
    TURN_SPEED: float = 0.3
    FORWARD_SPEED: float = 0.5

@dataclass
class SystemConfig:
    PORT: int = 8000
    HOST: str = '0.0.0.0'
    DATA_DIR: str = '/home/pi/vehicle_data'
    LOG_DIR: str = os.path.join(DATA_DIR, 'logs')
    MAP_DIR: str = os.path.join(DATA_DIR, 'maps')
    LOG_LEVEL: str = 'INFO'

class Config:
    def __init__(self):
        self.hardware = HardwareConfig()
        self.explorer = ExplorerConfig()
        self.system = SystemConfig()

config = Config()
