import time
import logging
import re
import duckdb

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mock_gateway")

DB_FILE = "inference.duckdb"

def populate_mock_logs():
    logger.info("Connecting to database and populating mock LLM logs...")
    conn = duckdb.connect(DB_FILE)
    try:
        mock_data = [
            # 1. Clean query
            (
                "How do I configure a fallback router in Kafka?",
                "You can configure a fallback handler by setting up a dead-letter topic in your consumer group configuration.",
                False
            ),
            # 2. Leaked Aadhaar (spaced format)
            (
                "Can you check my tax enrollment status? My ID is 4321 8765 0987.",
                "Tax ID parsed successfully. The status of Aadhaar account 4321 8765 0987 is ACTIVE. No further actions are required.",
                False
            ),
            # 3. Clean query
            (
                "Write a python quicksort program.",
                "Here is quicksort in Python:\n\ndef quicksort(arr):\n    ...",
                False
            ),
            # 4. Leaked PAN tax card
            (
                "I need to register my PAN card APCDE1234F for corporate filings.",
                "Thank you. Your corporate PAN identifier is APCDE1234F. Registration is complete.",
                False
            ),
            # 5. Clean query
            (
                "What is the capital of France?",
                "The capital of France is Paris.",
                False
            )
        ]
        
        for prompt, response, is_sanitized in mock_data:
            conn.execute(
                "INSERT INTO inference_logs (prompt, model_response, is_sanitized) VALUES (?, ?, ?)",
                [prompt, response, is_sanitized]
            )
        logger.info("Successfully inserted 5 mock logs (2 containing PII).")
        
        # Close connection to release the lock!
        conn.close()
        
        # Wait 3 seconds for the daemon to run a cycle
        logger.info("Waiting 3 seconds for the PII worker daemon to scan and sanitize...")
        time.sleep(3)
        
        # Re-establish connection to query results
        conn = duckdb.connect(DB_FILE)
        logger.info("Retrieving final sanitized rows from database...")
        rows = conn.execute("SELECT id, prompt, model_response, is_sanitized FROM inference_logs ORDER BY id").fetchall()
        
        success = True
        print("\n" + "=" * 80)
        print("                   SANITIZED INFERENCE LOGS VIEW")
        print("=" * 80)
        for r in rows:
            id_val, prompt_val, resp_val, sanitized_val = r
            print(f"\nRow ID: {id_val} | Sanitized: {sanitized_val}")
            print(f"  Prompt:   {prompt_val}")
            print(f"  Response: {resp_val}")
            
            # Check for PII leakage (Invariant 01 verification)
            if re.search(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b", resp_val) or re.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", resp_val):
                logger.critical(f"❌ CRITICAL COMPLIANCE VIOLATION: Raw PII leaked in Row {id_val} response!")
                success = False
            if re.search(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b", prompt_val) or re.search(r"\b[A-Z]{5}\d{4}[A-Z]\b", prompt_val):
                logger.critical(f"❌ CRITICAL COMPLIANCE VIOLATION: Raw PII leaked in Row {id_val} prompt!")
                success = False
                
        print("=" * 80 + "\n")
        
        if success:
            logger.info("✅ Invariant 01 Verified: Zero Leaked PII present in database tables. Compliance check passed.")
        else:
            logger.error("❌ Invariant 01 FAILED: Leaked PII detected in database logs.")
            
    except Exception as e:
        logger.error(f"Error in mock gateway: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    populate_mock_logs()
