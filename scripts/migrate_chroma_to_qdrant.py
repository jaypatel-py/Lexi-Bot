"""
Migrate vectors and metadata from ChromaDB to Qdrant.

Usage:
    python scripts/migrate_chroma_to_qdrant.py

Prerequisites:
    - ChromaDB running on localhost:8000 (docker-compose up -d)
    - Qdrant running on localhost:6333 (docker-compose up -d)
    - qdrant-client installed: pip install qdrant-client
"""

import chromadb
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import time


def migrate_chroma_to_qdrant(
    chroma_host: str = "localhost",
    chroma_port: str = "8000",
    qdrant_url: str = "http://localhost:6333",
    collection_name: str = "legal-docs",
    qdrant_collection_name: str = "legal-docs",
    vector_size: int = 384,
):
    """
    Migrate all vectors from a ChromaDB collection to Qdrant.

    Args:
        chroma_host: ChromaDB host
        chroma_port: ChromaDB port
        qdrant_url: Qdrant URL
        collection_name: Source ChromaDB collection name
        qdrant_collection_name: Target Qdrant collection name
        vector_size: Size of vectors (must match embedding model output)
    """
    print("=" * 60)
    print("ChromaDB to Qdrant Migration Script")
    print("=" * 60)

    # Connect to ChromaDB
    print(f"\n[1/5] Connecting to ChromaDB at {chroma_host}:{chroma_port}...")
    chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
    print(f"✓ Connected to ChromaDB: {chroma_client.heartbeat()}")

    # Connect to Qdrant
    print(f"\n[2/5] Connecting to Qdrant at {qdrant_url}...")
    qdrant_client = QdrantClient(url=qdrant_url)
    print(f"✓ Connected to Qdrant")

    # Get source collection
    print(f"\n[3/5] Getting ChromaDB collection '{collection_name}'...")
    try:
        chroma_collection = chroma_client.get_collection(name=collection_name)
    except Exception as e:
        print(f"✗ Collection '{collection_name}' not found in ChromaDB!")
        print(f"  Error: {e}")
        return

    # Get document count
    doc_count = chroma_collection.count()
    print(f"✓ Found {doc_count} documents in ChromaDB collection")

    # Create Qdrant collection if not exists
    print(f"\n[4/5] Creating Qdrant collection '{qdrant_collection_name}'...")
    try:
        qdrant_client.create_collection(
            collection_name=qdrant_collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        print(f"✓ Created Qdrant collection with vector_size={vector_size}, distance=COSINE")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"⚠ Collection '{qdrant_collection_name}' already exists, will use existing")
        else:
            print(f"✗ Error creating collection: {e}")
            return

    # Migrate data
    print(f"\n[5/5] Migrating {doc_count} documents from ChromaDB to Qdrant...")
    start_time = time.time()

    # Get all data from ChromaDB
    chroma_data = chroma_collection.get(include=["embeddings", "documents", "metadatas"])

    # Prepare points for Qdrant
    points = []
    for i, (id_, embedding, document, metadata) in enumerate(
        zip(
            chroma_data["ids"],
            chroma_data["embeddings"],
            chroma_data["documents"],
            chroma_data["metadatas"],
        )
    ):
        # Build payload with document and metadata
        payload = {
            "document": document,
            **metadata,
        }

        points.append(
            PointStruct(
                id=i,  # Use sequential integer IDs
                vector=embedding,
                payload=payload,
            )
        )

    # Batch insert into Qdrant
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        qdrant_client.upsert(collection_name=qdrant_collection_name, points=batch)
        print(f"  → Inserted {min(i + batch_size, len(points))}/{len(points)} documents")

    elapsed_time = time.time() - start_time
    print(f"\n✓ Migration completed in {elapsed_time:.2f} seconds")

    # Verify migration
    print(f"\n[Verification] Counting documents in Qdrant...")
    qdrant_count = qdrant_client.count(collection_name=qdrant_collection_name)
    print(f"✓ Qdrant collection has {qdrant_count.count} documents")

    if qdrant_count.count == doc_count:
        print(f"\n{'=' * 60}")
        print("✓ Migration successful! All documents transferred.")
        print(f"{'=' * 60}")
        print(f"\nAccess Qdrant Dashboard at: http://localhost:6333/dashboard")
        print(f"Collection name: {qdrant_collection_name}")
    else:
        print(f"\n⚠ Warning: Document count mismatch!")
        print(f"  ChromaDB: {doc_count}, Qdrant: {qdrant_count.count}")


if __name__ == "__main__":
    migrate_chroma_to_qdrant()
