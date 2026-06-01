import json
import logging
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
import duckdb

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingestion_engine")

# Pydantic schema model
class PrimaryEventModel(BaseModel):
    user_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

def process_payload(conn: duckdb.DuckDBPyConnection, json_data: str) -> bool:
    try:
        # Parse JSON raw string
        data = json.loads(json_data)
        
        # Validate against strict Pydantic model
        validated_event = PrimaryEventModel(**data)
        
        # Insert into primary_events table
        conn.execute(
            "INSERT INTO primary_events (user_id, event_type, amount, timestamp) VALUES (?, ?, ?, ?)",
            [
                validated_event.user_id,
                validated_event.event_type,
                validated_event.amount,
                validated_event.timestamp.isoformat()
            ]
        )
        return True
        
    except ValidationError as ve:
        # Capture schema drift or validation errors
        error_msg = str(ve).replace("\n", " | ")
        logger.warning(f"Validation failure for payload: {error_msg}")
        
        try:
            # Route to dead_letter_queue
            conn.execute(
                "INSERT INTO dead_letter_queue (raw_payload, error_message, timestamp) VALUES (?, ?, ?)",
                [json_data, error_msg, datetime.utcnow().isoformat()]
            )
        except Exception as db_err:
            logger.critical(f"Database write failure to DLQ: {db_err}")
            
        return False
        
    except json.JSONDecodeError as jde:
        # Handle malformed JSON event payload
        error_msg = f"Malformed JSON: {str(jde)}"
        logger.warning(f"JSON decode failure: {error_msg}")
        
        try:
            conn.execute(
                "INSERT INTO dead_letter_queue (raw_payload, error_message, timestamp) VALUES (?, ?, ?)",
                [json_data, error_msg, datetime.utcnow().isoformat()]
            )
        except Exception as db_err:
            logger.critical(f"Database write failure to DLQ: {db_err}")
            
        return False
        
    except Exception as e:
        # Catch any unexpected errors to satisfy Invariant 01 (never crash)
        error_msg = f"Unexpected Error: {str(e)}"
        logger.error(f"Ingestion process error: {error_msg}")
        
        try:
            conn.execute(
                "INSERT INTO dead_letter_queue (raw_payload, error_message, timestamp) VALUES (?, ?, ?)",
                [json_data, error_msg, datetime.utcnow().isoformat()]
            )
        except Exception as db_err:
            logger.critical(f"Database write failure to DLQ: {db_err}")
            
        return False
