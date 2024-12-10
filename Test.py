# test_minimal.py
from multiprocessing import Process

class TestProcess(Process):
    def __init__(self):
        super().__init__()
    
    def run(self):
        print("Test")

if __name__ == "__main__":
    p = TestProcess()
