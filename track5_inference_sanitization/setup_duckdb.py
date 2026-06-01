import duckdb
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_duckdb")

DB_FILE = "inference.duckdb"

def main():
    logger.info(f"Setting up DuckDB database file: {DB_FILE}")
    conn = duckdb.connect(DB_FILE)
    try:
        # Create sequence for auto-incrementing ID
        conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_log_id START 1;")
        
        # Create inference_logs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inference_logs (
                id INTEGER DEFAULT nextval('seq_log_id'),
                prompt TEXT NOT NULL,
                model_response TEXT NOT NULL,
                is_sanitized BOOLEAN DEFAULT FALSE
            );
        """)
        logger.info("Created 'inference_logs' table successfully.")
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
