import gpiod
import time
from config import config

def test_motor():
    chip = gpiod.Chip('gpiochip0')
    
    # Inicjalizacja pinów dla lewego koła
    fwd = chip.get_line(config.hardware.LEFT_MOTOR_FWD)
    bwd = chip.get_line(config.hardware.LEFT_MOTOR_BWD)
    en = chip.get_line(config.hardware.LEFT_MOTOR_EN)
    
    config_out = gpiod.LineRequest(
        consumer="test_motor",
        request_type=gpiod.LineRequest.DIRECTION_OUTPUT
    )
    
    # Konfiguracja pinów
    for pin in [fwd, bwd, en]:
        pin.request(config_out)
    
    try:
        print("Test przód")
        fwd.set_value(1)
        bwd.set_value(0)
        en.set_value(1)
        time.sleep(2)
        
        print("Stop")
        en.set_value(0)
        time.sleep(1)
        
        print("Test tył")
        fwd.set_value(0)
        bwd.set_value(1)
        en.set_value(1)
        time.sleep(2)
        
    finally:
        for pin in [fwd, bwd, en]:
            pin.set_value(0)

if __name__ == "__main__":
    test_motor()
