# test_gpio.py
import gpiod
import time

def test_gpio():
    try:
        # Print gpiod version
        print("Testing GPIO setup...")
        print(f"GPIOD version: {gpiod.__version__ if hasattr(gpiod, '__version__') else 'unknown'}")
        
        # Try to list available methods
        print("\nAvailable methods on Chip:")
        print([method for method in dir(gpiod.Chip) if not method.startswith('_')])
        
        # Try to open chip
        chip = gpiod.Chip('/dev/gpiochip0')
        print("\nSuccessfully opened chip")
        
        # Print available methods on chip instance
        print("\nAvailable methods on chip instance:")
        print([method for method in dir(chip) if not method.startswith('_')])
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_gpio()