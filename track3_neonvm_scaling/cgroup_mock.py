import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cgroup_mock")

MOCK_DIR = "./mock_cgroup/neonvm-1"

def init_mock_cgroup():
    logger.info(f"Initializing mock cgroup v2 directory: {MOCK_DIR}")
    os.makedirs(MOCK_DIR, exist_ok=True)
    
    # Initialize files
    # memory.max: 2GB (in bytes)
    max_path = os.path.join(MOCK_DIR, "memory.max")
    if not os.path.exists(max_path):
        with open(max_path, "w") as f:
            f.write("2147483648\n")
        logger.info("Initialized memory.max to 2GB (2147483648 bytes)")
        
    # memory.current: 500MB (in bytes)
    current_path = os.path.join(MOCK_DIR, "memory.current")
    if not os.path.exists(current_path):
        with open(current_path, "w") as f:
            f.write("524288000\n")
        logger.info("Initialized memory.current to 500MB (524288000 bytes)")
        
    # memory.events
    events_path = os.path.join(MOCK_DIR, "memory.events")
    if not os.path.exists(events_path):
        with open(events_path, "w") as f:
            f.write("low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n")
        logger.info("Initialized memory.events with zero counts")

if __name__ == "__main__":
    init_mock_cgroup()
