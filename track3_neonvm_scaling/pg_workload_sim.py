import os
import time
import logging
from pathlib import Path

# Configure logging with microsecond precision
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("pg_workload_sim")

MOCK_DIR = Path("./mock_cgroup/neonvm-1")
EVENTS_PATH = MOCK_DIR / "memory.events"
CURRENT_PATH = MOCK_DIR / "memory.current"
MAX_PATH = MOCK_DIR / "memory.max"

def read_file_int(path: Path) -> int:
    with open(path, "r") as f:
        return int(f.read().strip())

def write_file_int(path: Path, val: int):
    with open(path, "w") as f:
        f.write(f"{val}\n")

def parse_events(content: str) -> dict:
    events = {}
    for line in content.strip().split("\n"):
        parts = line.split()
        if len(parts) == 2:
            events[parts[0]] = int(parts[1])
    return events

def write_events(path: Path, events: dict):
    lines = [f"{k} {v}" for k, v in events.items()]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

def main():
    logger.info("Initializing Postgres Database workload simulation...")
    
    if not MOCK_DIR.exists():
        logger.error("Mock cgroup directory not found. Please run cgroup_mock.py first.")
        return

    # Read current limits
    initial_max = read_file_int(MAX_PATH)
    logger.info(f"Initial DB memory limit (memory.max): {initial_max} bytes ({initial_max / (1024**3):.2f} GB)")

    # Set initial memory current
    write_file_int(CURRENT_PATH, 500 * 1024 * 1024)
    logger.info("Simulating idle database memory state: 500MB")

    # Step 1: Start SQL Join workload (Rapid memory increase)
    logger.info("🚀 [Workload] Triggering massive SQL join query on agent table...")
    time.sleep(0.5)

    # We will simulate memory usage rising from 500MB to 1.9GB in steps
    target_steps = [800, 1100, 1400, 1700, 1950]  # in MB
    for step in target_steps:
        mem_bytes = step * 1024 * 1024
        write_file_int(CURRENT_PATH, mem_bytes)
        logger.info(f"[Workload] Query memory footprint scaled to {step}MB...")
        time.sleep(0.1)

    # Step 2: Check if memory pressure is high
    current_mem = read_file_int(CURRENT_PATH)
    current_max = read_file_int(MAX_PATH)
    
    logger.info(f"[Workload] Memory footprint: {current_mem} bytes. Max capacity: {current_max} bytes.")
    
    # Check if we are above 90% usage
    if current_mem >= (0.90 * current_max):
        logger.info("⚠️ [Workload] Memory pressure approaching 90% threshold! Generating cgroup v2 high event...")
        
        # Read events, increment high counter, write events
        with open(EVENTS_PATH, "r") as f:
            events = parse_events(f.read())
            
        events["high"] = events.get("high", 0) + 1
        
        logger.info(f"🔔 [Cgroup Event] memory.events 'high' counter set to {events['high']}")
        write_events(EVENTS_PATH, events)
        
        # Wait a brief moment to allow the monitor daemon to respond
        # According to performance Invariant 01, this response should be < 50ms.
        # We sleep 100ms and then check if memory.max has increased.
        time.sleep(0.1)
        
        # Step 3: Check if OOM was avoided
        new_max = read_file_int(MAX_PATH)
        if new_max > current_max:
            logger.info(
                f"✅ [OOM AVOIDED] Success! Monitor resized database memory ceiling from "
                f"{current_max} to {new_max} bytes (+1GB) in response to the high pressure event."
            )
            # Simulate query completing successfully with expanded memory
            logger.info("🎉 [Workload] SQL Join completed successfully. Query results returned to Databricks Agent.")
        else:
            logger.critical("❌ [OOM CRASH] Database process terminated by Linux kernel OOM Killer (OOM-Killed)!")
            logger.critical("Reason: memory.max limit was not adjusted in time by the monitor.")
    else:
        logger.info("[Workload] Query finished. Memory usage did not reach pressure threshold.")

if __name__ == "__main__":
    main()
