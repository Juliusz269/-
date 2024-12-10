import logging
import os
from config import config

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.system.LOG_LEVEL))
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    os.makedirs(config.system.LOG_DIR, exist_ok=True)
    fh = logging.FileHandler(
        os.path.join(config.system.LOG_DIR, f'{name}.log')
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger
