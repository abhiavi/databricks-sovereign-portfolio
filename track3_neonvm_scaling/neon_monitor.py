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
logger = logging.getLogger("neon_monitor")

MOCK_DIR = Path("./mock_cgroup/neonvm-1")
EVENTS_PATH = MOCK_DIR / "memory.events"
MAX_PATH = MOCK_DIR / "memory.max"

COOLDOWN_PERIOD = 5.0  # seconds

def parse_events(content: str) -> dict:
    events = {}
    for line in content.strip().split("\n"):
        parts = line.split()
        if len(parts) == 2:
            events[parts[0]] = int(parts[1])
    return events

def main():
    logger.info("Starting NeonVM memory event monitor daemon...")
    
    if not EVENTS_PATH.exists():
        logger.error(f"Event file {EVENTS_PATH} does not exist. Please run cgroup_mock.py first.")
        return

    # Cache the initial event state
    try:
        with open(EVENTS_PATH, "r") as f:
            initial_content = f.read()
        events_cache = parse_events(initial_content)
        logger.info(f"Initial event state cached: {events_cache}")
    except Exception as e:
        logger.error(f"Error reading events file: {e}")
        return

    last_scale_time = 0.0

    logger.info("Monitoring memory.events loop started (5ms check interval)...")
    while True:
        try:
            # High-frequency polling loop
            time.sleep(0.005)
            
            with open(EVENTS_PATH, "r") as f:
                content = f.read()
                
            current_events = parse_events(content)
            
            # Check if 'high' event count has increased
            prev_high = events_cache.get("high", 0)
            curr_high = current_events.get("high", 0)
            
            if curr_high > prev_high:
                # We detected a pressure event!
                t_detect = time.time()
                events_cache = current_events  # Update cache
                
                # Check cooldown
                if t_detect - last_scale_time < COOLDOWN_PERIOD:
                    logger.warning(f"Memory pressure event detected, but monitor is in cooldown (last scale was {t_detect - last_scale_time:.2f}s ago). Ignoring.")
                    continue
                
                # Scale up immediately
                t_start = time.perf_counter_ns()
                
                # Read memory.max
                with open(MAX_PATH, "r") as f_max:
                    max_content = f_max.read().strip()
                current_max = int(max_content)
                
                # Add 1GB in bytes (1073741824 bytes)
                new_max = current_max + 1073741824
                
                # Write back to memory.max
                with open(MAX_PATH, "w") as f_max:
                    f_max.write(f"{new_max}\n")
                    
                t_end = time.perf_counter_ns()
                
                # Calculate duration
                reaction_time_ns = t_end - t_start
                reaction_time_us = reaction_time_ns / 1000.0
                
                last_scale_time = t_detect
                logger.info(
                    f"🚨 [SCALE EVENT] Memory pressure detected ('high' counter incremented to {curr_high}). "
                    f"Scaled memory.max from {current_max} to {new_max} bytes (+1GB). "
                    f"Reaction time: {reaction_time_us:.2f} microseconds."
                )
                
        except KeyboardInterrupt:
            logger.info("Monitor daemon stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
