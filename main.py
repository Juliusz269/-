import asyncio
from aiohttp import web
import json
import os
from multiprocessing import Queue, Event
from hardware.processes import LiDARProcess, CameraProcess, MotorProcess, ExplorerProcess
from config import config
from utils.logger import setup_logger
from typing import Dict, Any, Optional, List

logger = setup_logger('main')

class VehicleController:
    def __init__(self):
        self.stop_event = Event()
        self.data_queue = Queue()
        self.scan_queue = Queue()
        self.motor_queue = Queue()
        self.mode = 'manual'
        
        # Store latest data as class attributes
        self.latest_frame: Optional[str] = None
        self.latest_map: Optional[list] = None
        self.latest_position: Optional[Dict[str, float]] = None
        
        # Initialize processes
        self._init_processes()
        
    def _init_processes(self) -> None:
        """Initialize all vehicle control processes"""
        self.processes = {
            'lidar': LiDARProcess(self.scan_queue, self.stop_event),
            'camera': CameraProcess(self.data_queue, self.stop_event),
            'motor': MotorProcess(self.motor_queue, self.stop_event)
        }
        
    def _validate_speed(self, speed: float) -> bool:
        """Validate motor speed value"""
        return -1.0 <= speed <= 1.0

    async def start(self) -> web.Application:
        """Initialize and start the web application"""
        # Create required directories
        for directory in [config.system.DATA_DIR, config.system.LOG_DIR, config.system.MAP_DIR]:
            os.makedirs(directory, exist_ok=True)
        
        # Start all processes
        for process in self.processes.values():
            process.start()
        logger.info("All processes started successfully")
        
        # Start data processing task
        asyncio.create_task(self._process_data())
        
        # Setup web application routes
        app = web.Application()
        app.router.add_routes([
            web.get('/health', self.health_check),
            web.post('/control', self.handle_control),
            web.post('/mode', self.handle_mode),
            web.get('/camera', self.get_camera),
            web.get('/map', self.get_map),
            web.get('/position', self.get_position),
            web.post('/emergency', self.handle_emergency),
            web.get('/status', self.get_status)
        ])
        
        # Add cleanup callback
        app.on_shutdown.append(self._cleanup)
        
        return app

    async def _cleanup(self, app: web.Application) -> None:
        """Cleanup handler for graceful shutdown"""
        await self.stop()

    async def stop(self) -> None:
        """Stop all processes and cleanup"""
        logger.info("Stopping vehicle controller...")
        self.stop_event.set()
        
        for process in self.processes.values():
            try:
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
            except Exception as e:
                logger.error(f"Error stopping process: {e}")
        
        logger.info("Vehicle controller stopped")

    async def _process_data(self) -> None:
        """Process incoming data from various queues"""
        while True:
            try:
                if not self.data_queue.empty():
                    data_type, data = self.data_queue.get_nowait()
                    
                    if data_type == 'frame':
                        self.latest_frame = data
                    elif data_type == 'map':
                        self.latest_map = data['data']
                        self.latest_position = {
                            'x': data['position'][0],
                            'y': data['position'][1],
                            'orientation': data['orientation']
                        }
            except Exception as e:
                logger.error(f"Error processing data: {e}")
            
            await asyncio.sleep(0.01)

    async def handle_control(self, request: web.Request) -> web.Response:
        """Handle manual control commands"""
        if self.mode != 'manual':
            return web.Response(status=400, text='Not in manual mode')
        
        try:
            data = await request.json()
            left = float(data['left'])
            right = float(data['right'])
            
            if not (self._validate_speed(left) and self._validate_speed(right)):
                return web.Response(status=400, text='Invalid speed values')
                
            self.motor_queue.put(('move', (left, right)))
            return web.Response(text='OK')
        except ValueError:
            return web.Response(status=400, text='Invalid speed format')
        except Exception as e:
            logger.error(f"Control error: {e}")
            return web.Response(status=500, text=str(e))

    async def handle_mode(self, request: web.Request) -> web.Response:
        """Handle mode changes between manual and explore"""
        try:
            data = await request.json()
            new_mode = data['mode']
            
            if new_mode not in ['manual', 'explore']:
                return web.Response(status=400, text='Invalid mode')
                
            if new_mode == self.mode:
                return web.Response(text='Mode unchanged')
                
            if new_mode == 'explore':
                self.processes['explorer'] = ExplorerProcess(
                    self.scan_queue, self.motor_queue, self.data_queue, self.stop_event
                )
                self.processes['explorer'].start()
            else:
                if 'explorer' in self.processes:
                    self.processes['explorer'].terminate()
                    self.processes['explorer'].join()
                    del self.processes['explorer']
                    
            self.mode = new_mode
            return web.Response(text=f'Mode changed to {new_mode}')
            
        except Exception as e:
            logger.error(f"Mode change error: {e}")
            return web.Response(status=500, text=str(e))

    async def handle_emergency(self, request: web.Request) -> web.Response:
        """Handle emergency stop command"""
        try:
            self.motor_queue.put(('emergency_stop', None))
            if 'explorer' in self.processes:
                self.processes['explorer'].terminate()
                self.processes['explorer'].join()
                del self.processes['explorer']
            self.mode = 'manual'
            return web.Response(text='Emergency stop activated')
        except Exception as e:
            logger.error(f"Emergency stop error: {e}")
            return web.Response(status=500, text=str(e))

    async def get_camera(self, request: web.Request) -> web.Response:
        """Get latest camera frame"""
        if self.latest_frame:
            return web.json_response({'frame': self.latest_frame})
        return web.Response(status=404, text='No camera frame available')

    async def get_map(self, request: web.Request) -> web.Response:
        """Get latest map data"""
        if self.latest_map is not None:
            return web.json_response({'map': self.latest_map})
        return web.Response(status=404, text='No map data available')

    async def get_position(self, request: web.Request) -> web.Response:
        """Get latest position data"""
        if self.latest_position:
            return web.json_response(self.latest_position)
        return web.Response(status=404, text='No position data available')

    async def health_check(self, request: web.Request) -> web.Response:
        """Simple health check endpoint"""
        return web.Response(text='OK')

    async def get_status(self, request: web.Request) -> web.Response:
        """Get current status of all processes"""
        status = {
            'mode': self.mode,
            'camera_active': self.processes['camera'].is_alive(),
            'lidar_active': self.processes['lidar'].is_alive(),
            'motor_active': self.processes['motor'].is_alive(),
            'explorer_active': self.processes.get('explorer', {}).is_alive() if 'explorer' in self.processes else False
        }
        return web.json_response(status)

async def main() -> None:
    """Main application entry point"""
    controller = VehicleController()
    app = await controller.start()
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.system.HOST, config.system.PORT)
    
    try:
        await site.start()
        logger.info(f"Server started at http://{config.system.HOST}:{config.system.PORT}")
        
        # Wait for shutdown signal
        shutdown_event = asyncio.Event()
        await shutdown_event.wait()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal...")
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
