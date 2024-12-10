import os
from multiprocessing import Process, Queue, Event
from typing import List, Tuple, Optional
import numpy as np
import cv2
import base64
from rplidar import RPLidar
from picamera2 import Picamera2
from libcamera import Transform
import time
from config import config
from utils.logger import setup_logger
import gpiod

class LiDARProcess(Process):
    def __init__(self, data_queue: Queue, stop_event: Event):
        super().__init__()
        self.queue = data_queue
        self.stop_event = stop_event
        self.logger = setup_logger('lidar')
        
        # Configuration parameters
        self.max_retries = 5
        self.retry_delay = 3
        self.min_quality = 15
        self.measurement_delay = 0.1

    def _init_lidar(self) -> RPLidar:
        """Initialize LiDAR with proper error handling."""
        try:
            # Inicjalizacja z parametrami z konfiguracji
            lidar = RPLidar(
                port=config.hardware.LIDAR_PORT,
                baudrate=config.hardware.LIDAR_BAUDRATE
            )
            
            # Reset i restart urządzenia
            lidar.stop()
            lidar.disconnect()
            time.sleep(1)
            
            lidar.connect()
            lidar.start_motor()
            time.sleep(1)  # Czas na rozpędzenie silnika
            
            # Pobranie informacji o urządzeniu
            info = lidar.get_info()
            health = lidar.get_health()
            self.logger.info(f"LiDAR info: {info}")
            self.logger.info(f"LiDAR health: {health}")
            
            return lidar

        except Exception as e:
            self.logger.error(f"LiDAR initialization error: {e}")
            raise

    def _process_scan(self, scan_data) -> Optional[List[Tuple[float, float]]]:
        """Process raw scan data into usable format."""
        try:
            processed_scan = []
            for quality, angle, distance in scan_data:
                # Konwersja odległości na metry i filtrowanie po jakości
                if quality >= self.min_quality:
                    processed_scan.append((angle, distance/1000.0))
            
            return processed_scan if processed_scan else None

        except Exception as e:
            self.logger.error(f"Error processing scan data: {e}")
            return None

    def _cleanup_lidar(self, lidar: Optional[RPLidar]) -> None:
        """Safely clean up LiDAR resources."""
        if lidar is not None:
            try:
                lidar.stop_motor()
                lidar.stop()
                lidar.disconnect()
            except Exception as e:
                self.logger.error(f"Error during LiDAR cleanup: {e}")

    def run(self):
        """Main process loop."""
        retry_count = 0
        lidar = None
        
        while not self.stop_event.is_set() and retry_count < self.max_retries:
            try:
                if lidar is None:
                    lidar = self._init_lidar()
                    self.logger.info("LiDAR process started successfully")
                    retry_count = 0
                
                for scan in lidar.iter_scans():
                    if self.stop_event.is_set():
                        break
                        
                    processed_scan = self._process_scan(scan)
                    if processed_scan:
                        self.queue.put(('scan', processed_scan))
                    
                    time.sleep(self.measurement_delay)
                    
            except Exception as e:
                self.logger.error(f"LiDAR error: {e}")
                retry_count += 1
                self._cleanup_lidar(lidar)
                lidar = None
                
                if retry_count < self.max_retries:
                    self.logger.info(f"Retrying LiDAR initialization (attempt {retry_count + 1}/{self.max_retries})")
                    time.sleep(self.retry_delay)
                else:
                    self.logger.error("Max retry attempts reached, stopping LiDAR process")
                    break
        
        self._cleanup_lidar(lidar)
        self.logger.info("LiDAR process stopped")


class MotorProcess(Process):
    def __init__(self, command_queue: Queue, stop_event: Event):
        super().__init__()
        self.queue = command_queue
        self.stop_event = stop_event
        self.logger = setup_logger('motor')
        self.logger.info("Motor prosess initialized")
    def _init_gpio(self):
        """Initialize GPIO pins for motor control."""
        print("Starting GPIO initialization...")  # Basic print for debugging
        try:
            print("About to open GPIO chip...")
            chip = gpiod.Chip('/dev/gpiochip0')
            print("Opened GPIO chip successfully")
            self.logger.info("Opened GPIO chip")
            
            pin_configs = [
                (config.hardware.LEFT_MOTOR_FWD, 'left_fwd'),
                (config.hardware.LEFT_MOTOR_BWD, 'left_bwd'),
                (config.hardware.LEFT_MOTOR_EN, 'left_en'),
                (config.hardware.RIGHT_MOTOR_FWD, 'right_fwd'),
                (config.hardware.RIGHT_MOTOR_BWD, 'right_bwd'),
                (config.hardware.RIGHT_MOTOR_EN, 'right_en')
            ]
            print(f"Pin configs created: {pin_configs}")

            request_config = {str(pin[0]): None for pin in pin_configs}
            print(f"Request config created: {request_config}")
            
            self.logger.info(f"Requesting lines with config: {request_config}")
            lines = chip.request_lines(request_config)
            print("Lines requested successfully")
            self.logger.info("Successfully requested GPIO lines")
            
            return lines

        except Exception as e:
            print(f"Error in GPIO initialization: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            self.logger.error(f"GPIO initialization error: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    def run(self):
        """Main process loop."""
        try:
            self.logger.info("Starting motor process run method...")  
            pins = None
            
            self.logger.info("About to initialize GPIO...") 
            pins = self._init_gpio()
            self.logger.info("Motor GPIO initialized successfully")
            
            while not self.stop_event.is_set():
                if not self.queue.empty():
                    cmd, data = self.queue.get()
                    self.logger.info(f"Received command: {cmd}")  
                    
                    if cmd == 'move':
                        left, right = data
                        self._set_motors(pins, left, right)
                    elif cmd == 'emergency_stop':
                        self._emergency_stop(pins)
                        
                time.sleep(0.01)
                
        except Exception as e:
            self.logger.error(f"Error in motor run method: {e}")
            # Also print the full traceback
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            if pins:
                self._emergency_stop(pins)
                for pin in pins.values():
                    try:
                        pin.release()
                    except Exception as e:
                        self.logger.error(f"Error releasing pin: {e}")
            self.logger.info("Motor process stopped")
            
class CameraProcess(Process):
    def __init__(self, data_queue: Queue, stop_event: Event):
        super().__init__()
        self.queue = data_queue
        self.stop_event = stop_event
        self.logger = setup_logger('camera')
        # Store config values locally since multiprocessing doesn't share global state
        self.resolution = config.hardware.CAMERA_RESOLUTION
        self.framerate = config.hardware.CAMERA_FRAMERATE
    
    def run(self):
        try:
            camera = Picamera2()
            camera_config = camera.create_still_configuration(
                main={"size": self.resolution}
            )
            camera.configure(camera_config)
            camera.start()
            self.logger.info("Camera process started")
            
            while not self.stop_event.is_set():
                frame = camera.capture_array()
                success, buffer = cv2.imencode('.jpg', frame)
                if success:
                    frame_data = base64.b64encode(buffer).decode('utf-8')
                    self.queue.put(('frame', frame_data))
                time.sleep(1/self.framerate)
                
        except Exception as e:
            self.logger.error(f"Camera error: {e}")
        finally:
            if 'camera' in locals():
                camera.stop()
            
class ExplorerProcess(Process):
    def __init__(self, scan_queue: Queue, motor_queue: Queue, data_queue: Queue, stop_event: Event):
        super().__init__()
        self.scan_queue = scan_queue
        self.motor_queue = motor_queue
        self.data_queue = data_queue
        self.stop_event = stop_event
        self.logger = setup_logger('explorer')

    def run(self):
        map_data = np.zeros((config.explorer.MAP_SIZE, config.explorer.MAP_SIZE))
        position = np.array([config.explorer.MAP_SIZE//2, config.explorer.MAP_SIZE//2])
        orientation = 0.0
        self.logger.info("Explorer process started")

        while not self.stop_event.is_set():
            if not self.scan_queue.empty():
                _, scan = self.scan_queue.get()
                nearest = float('inf')

                for angle, dist in scan:
                    if -30 <= angle <= 30 and dist < nearest:
                        nearest = dist

                    rad_angle = np.radians(angle + orientation)
                    x = int(position[0] + (dist * np.cos(rad_angle) / config.explorer.RESOLUTION))
                    y = int(position[1] + (dist * np.sin(rad_angle) / config.explorer.RESOLUTION))

                    if 0 <= x < config.explorer.MAP_SIZE and 0 <= y < config.explorer.MAP_SIZE:
                        map_data[y, x] = 1

                if nearest < config.explorer.MIN_DISTANCE:
                    self.motor_queue.put(('move', (-config.explorer.TURN_SPEED, config.explorer.TURN_SPEED)))
                    orientation = (orientation + 5) % 360
                else:
                    self.motor_queue.put(('move', (config.explorer.FORWARD_SPEED, config.explorer.FORWARD_SPEED)))
                    position[0] += 0.05 * np.cos(np.radians(orientation))
                    position[1] += 0.05 * np.sin(np.radians(orientation))

                self.data_queue.put(('map', {
                    'data': map_data.tolist(),
                    'position': position.tolist(),
                    'orientation': orientation
                }))

            time.sleep(0.1)

        self.motor_queue.put(('emergency_stop', None))
        self.logger.info("Explorer process stopped")
