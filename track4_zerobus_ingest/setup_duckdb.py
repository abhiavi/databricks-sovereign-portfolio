import duckdb
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_duckdb")

DB_FILE = "zerobus.duckdb"

def setup_database():
    logger.info(f"Setting up DuckDB database file: {DB_FILE}")
    conn = duckdb.connect(DB_FILE)
    try:
        # Create sequences for auto-incrementing primary keys
        conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_primary_id START 1;")
        conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_dlq_id START 1;")
        
        # Create primary_events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS primary_events (
                id INTEGER DEFAULT nextval('seq_primary_id'),
                user_id VARCHAR NOT NULL,
                event_type VARCHAR NOT NULL,
                amount DOUBLE NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created 'primary_events' table successfully.")
        
        # Create dead_letter_queue table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER DEFAULT nextval('seq_dlq_id'),
                raw_payload VARCHAR NOT NULL,
                error_message VARCHAR NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created 'dead_letter_queue' table successfully.")
        
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()
