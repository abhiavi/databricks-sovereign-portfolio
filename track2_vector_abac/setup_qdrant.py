import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("setup_qdrant")

def main():
    logger.info("Initializing Qdrant client with local persistent storage...")
    # Use persistent path so that vector_proxy.py can read the database
    client = QdrantClient(path="./qdrant_data")
    
    collection_name = "enterprise_docs"
    logger.info(f"Creating collection '{collection_name}' if it does not exist...")
    
    # Recreate collection to ensure a clean state
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=4, distance=Distance.COSINE)
    )
    
    # 3 mock document vectors (2 tagged 'FINANCE', 1 tagged 'PUBLIC')
    # Vector size: 4
    points = [
        PointStruct(
            id=1,
            vector=[0.9, 0.1, 0.1, 0.1],
            payload={
                "title": "Q1 Financial Results",
                "content": "Sensitive financial spreadsheet showing 15% revenue growth.",
                "tags": ["FINANCE"]
            }
        ),
        PointStruct(
            id=2,
            vector=[0.8, 0.2, 0.1, 0.1],
            payload={
                "title": "Corporate Budget 2026",
                "content": "Internal departmental allocations and salary forecasts.",
                "tags": ["FINANCE"]
            }
        ),
        PointStruct(
            id=3,
            vector=[0.1, 0.1, 0.9, 0.1],
            payload={
                "title": "Public Press Release",
                "content": "General public statement welcoming new board members.",
                "tags": ["PUBLIC"]
            }
        )
    ]
    
    logger.info(f"Inserting {len(points)} mock points into '{collection_name}'...")
    client.upsert(
        collection_name=collection_name,
        points=points
    )
    
    logger.info("Database setup complete.")

if __name__ == "__main__":
    main()
