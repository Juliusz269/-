import pytest
import asyncio
from aiohttp import web
from multiprocessing import Queue, Event
import numpy as np
import base64
import cv2
from unittest.mock import Mock, patch

from main import VehicleController
from hardware.processes import LiDARProcess, CameraProcess, MotorProcess, ExplorerProcess
from config import config
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
@pytest.fixture
async def controller():
    ctrl = VehicleController()
    app = await ctrl.start()
    yield ctrl
    await ctrl.stop()

@pytest.fixture
async def client(aiohttp_client, controller):
    app = await controller.start()
    return await aiohttp_client(app)

class TestHardwareProcesses:
    def test_motor_process(self):
        stop_event = Event()
        command_queue = Queue()
        
        with patch('libgpiod.Chip') as mock_chip:
            process = MotorProcess(command_queue, stop_event)
            process.start()
            
            # Test forward movement
            command_queue.put(('move', (0.5, 0.5)))
            asyncio.sleep(0.1)
            
            # Test emergency stop
            command_queue.put(('emergency_stop', None))
            asyncio.sleep(0.1)
            
            stop_event.set()
            process.join(timeout=1)
            assert not process.is_alive()
    
    def test_lidar_process(self):
        stop_event = Event()
        data_queue = Queue()
        
        with patch('rplidar.RPLidar') as mock_lidar:
            mock_lidar.return_value.iter_scans.return_value = [
                [(15, 0, 1000), (15, 90, 1000)]
            ]
            
            process = LiDARProcess(data_queue, stop_event)
            process.start()
            
            asyncio.sleep(0.2)
            assert not data_queue.empty()
            data_type, scan = data_queue.get()
            assert data_type == 'scan'
            assert len(scan) > 0
            
            stop_event.set()
            process.join(timeout=1)
            assert not process.is_alive()

    def test_camera_process(self):
        stop_event = Event()
        data_queue = Queue()
        
        with patch('picamera2.Picamera2') as mock_camera:
            mock_camera.return_value.capture_array.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
            
            process = CameraProcess(data_queue, stop_event)
            process.start()
            
            asyncio.sleep(0.2)
            assert not data_queue.empty()
            data_type, frame = data_queue.get()
            assert data_type == 'frame'
            assert isinstance(frame, str)  # Base64 encoded
            
            stop_event.set()
            process.join(timeout=1)
            assert not process.is_alive()

class TestAPI:
    async def test_health_check(self, client):
        resp = await client.get('/health')
        assert resp.status == 200
        assert await resp.text() == 'OK'
    
    async def test_control(self, client):
        # Test valid control
        resp = await client.post('/control', json={'left': 0.5, 'right': 0.5})
        assert resp.status == 200
        
        # Test invalid values
        resp = await client.post('/control', json={'left': 1.5, 'right': 0.5})
        assert resp.status == 400
    
    async def test_mode_change(self, client):
        # Test mode change to explore
        resp = await client.post('/mode', json={'mode': 'explore'})
        assert resp.status == 200
        
        # Test invalid mode
        resp = await client.post('/mode', json={'mode': 'invalid'})
        assert resp.status == 400
    
    async def test_emergency_stop(self, client):
        resp = await client.post('/emergency')
        assert resp.status == 200

class TestIntegration:
    async def test_full_workflow(self, client):
        # Start in manual mode
        resp = await client.get('/status')
        assert resp.status == 200
        status = await resp.json()
        assert status['mode'] == 'manual'
        
        # Send movement command
        resp = await client.post('/control', json={'left': 0.3, 'right': 0.3})
        assert resp.status == 200
        
        # Switch to explore mode
        resp = await client.post('/mode', json={'mode': 'explore'})
        assert resp.status == 200
        
        # Check explorer is running
        resp = await client.get('/status')
        status = await resp.json()
        assert status['explorer_active'] == True
        
        # Emergency stop
        resp = await client.post('/emergency')
        assert resp.status == 200
        
        # Verify back in manual mode
        resp = await client.get('/status')
        status = await resp.json()
        assert status['mode'] == 'manual'

if __name__ == '__main__':
    pytest.main(['-v'])
