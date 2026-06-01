import json
import random
import logging
import duckdb
from datetime import datetime
from ingestion_engine import process_payload

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("stream_generator")

DB_FILE = "zerobus.duckdb"

def generate_payloads(count: int = 100) -> list:
    payloads = []
    
    event_types = ["click", "purchase", "login", "logout", "view"]
    user_ids = [f"usr_{random.randint(1000, 9999)}" for _ in range(10)]
    
    for i in range(count):
        # 20% corruption probability: every 5th item is corrupted
        is_corrupted = (i % 5 == 0)
        
        if not is_corrupted:
            # Compliant event payload
            payload = {
                "user_id": random.choice(user_ids),
                "event_type": random.choice(event_types),
                "amount": round(random.uniform(5.0, 500.0), 2),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Corrupted payload to simulate schema drift
            drift_type = random.choice(["missing_field", "type_mismatch", "invalid_json"])
            
            if drift_type == "missing_field":
                # Missing required field 'user_id'
                payload = {
                    "event_type": random.choice(event_types),
                    "amount": round(random.uniform(5.0, 500.0), 2),
                    "timestamp": datetime.utcnow().isoformat()
                }
            elif drift_type == "type_mismatch":
                # Value of 'amount' is a string instead of a float
                payload = {
                    "user_id": random.choice(user_ids),
                    "event_type": random.choice(event_types),
                    "amount": "NOT_A_FLOAT_VALUE",
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                # Malformed JSON (string format error)
                payloads.append("{'invalid': 'json', missing_quotes}")
                continue
                
        payloads.append(json.dumps(payload))
        
    return payloads

def run_ingestion_test():
    logger.info("Starting ingestion stream simulation...")
    
    # Establish connection
    conn = duckdb.connect(DB_FILE)
    
    try:
        # Generate 100 payloads (20% corrupted)
        payloads = generate_payloads(100)
        logger.info(f"Generated {len(payloads)} payloads for the stream.")
        
        # Process in a loop passing the single connection
        valid_count = 0
        invalid_count = 0
        
        for payload in payloads:
            success = process_payload(conn, payload)
            if success:
                valid_count += 1
            else:
                invalid_count += 1
                
        logger.info(f"Processing complete: {valid_count} valid events, {invalid_count} drifted/invalid events.")
        
        # Query database to verify Invariant 02 (Zero Data Loss)
        primary_rows = conn.execute("SELECT COUNT(*) FROM primary_events").fetchone()[0]
        dlq_rows = conn.execute("SELECT COUNT(*) FROM dead_letter_queue").fetchone()[0]
        
        total_rows = primary_rows + dlq_rows
        
        logger.info(f"Database query counts: primary_events = {primary_rows}, dead_letter_queue = {dlq_rows}")
        logger.info(f"Verification Formula: {primary_rows} (Primary) + {dlq_rows} (DLQ) = {total_rows} (Total Rows)")
        
        # Assert Invariant 02
        assert total_rows == 100, f"Invariant violation: Expected 100 total rows, got {total_rows}!"
        logger.info("✅ Invariant 02 verified successfully: Primary + DLQ = 100. No data was lost during ingestion.")
        
    except Exception as e:
        logger.error(f"Error during ingestion test execution: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_ingestion_test()
