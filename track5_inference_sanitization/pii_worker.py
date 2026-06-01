import re
import time
import logging
import duckdb

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("pii_worker")

DB_FILE = "inference.duckdb"

# Compile regex patterns for efficiency
PAN_REGEX = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
AADHAAR_REGEX = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")

def redact_text(text: str) -> tuple[str, bool]:
    redacted = text
    modified = False
    
    # Redact PAN formats
    if PAN_REGEX.search(redacted):
        redacted = PAN_REGEX.sub("[REDACTED_PII]", redacted)
        modified = True
        
    # Redact Aadhaar formats
    if AADHAAR_REGEX.search(redacted):
        redacted = AADHAAR_REGEX.sub("[REDACTED_PII]", redacted)
        modified = True
        
    return redacted, modified

def sanitize_inference_logs(conn: duckdb.DuckDBPyConnection) -> int:
    # Retrieve all unsanitized logs
    rows = conn.execute(
        "SELECT id, prompt, model_response FROM inference_logs WHERE is_sanitized = FALSE"
    ).fetchall()
    
    if not rows:
        return 0
        
    processed_count = 0
    t_start = time.perf_counter_ns()
    
    for id_val, prompt, model_response in rows:
        # Redact model_response and prompt
        sanitized_response, resp_modified = redact_text(model_response)
        sanitized_prompt, prompt_modified = redact_text(prompt)
        
        # In-place update to DB, setting is_sanitized to True
        conn.execute(
            "UPDATE inference_logs SET prompt = ?, model_response = ?, is_sanitized = TRUE WHERE id = ?",
            [sanitized_prompt, sanitized_response, id_val]
        )
        processed_count += 1
        
    t_end = time.perf_counter_ns()
    duration_ms = (t_end - t_start) / 1000000.0
    
    if processed_count > 0:
        logger.info(f"Processed {processed_count} logs in {duration_ms:.2f}ms (Average {duration_ms/processed_count:.2f}ms per row).")
        
    return processed_count

def main():
    logger.info("Starting PII Sanitization worker daemon...")
    
    while True:
        try:
            # Connect to database
            # In-process connection (must close after each query cycle to allow concurrent connections)
            conn = duckdb.connect(DB_FILE)
            try:
                sanitize_inference_logs(conn)
            finally:
                conn.close()
                
            time.sleep(2)
        except KeyboardInterrupt:
            logger.info("Sanitization worker stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
