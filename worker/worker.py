import os
import json
import time
import pika
import sqlalchemy
import sys
sys.path.insert(0, '/app')
from shared.embeddings import embed_chunks
from minio import Minio
import pymupdf4llm
import fitz

DB_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/seng468')
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
QUEUE_NAME = 'document_processing'

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
BUCKET_NAME = os.environ.get("BUCKET_NAME")

def get_minio_client():
    return Minio(
        MINIO_ENDPOINT,
        MINIO_ACCESS_KEY,
        MINIO_SECRET_KEY,
        secure=False #cuz its local
    )

def extract_text_chunks(pdf_bytes, chunk_size, overlap) -> list:
    
    doc = fitz.Document(stream=pdf_bytes, filetype="pdf")
    # this reads directly rather than saving a temp file

    text = pymupdf4llm.to_markdown(doc)
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk: chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

def save_chunks(engine, document_id, user_id, chunks, vectors) -> None:

    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
            {"doc_id": document_id}
        )
        for i, (chunk_text, embedding) in enumerate(zip(chunks, vectors)):
            conn.execute(
                sqlalchemy.text(
                    """
                    INSERT INTO document_chunks (document_id, user_id, chunk_index, chunk_text, embedding)
                    VALUES (:doc_id, :user_id, :idx, :text, :embedding)
                    """
                ),
                {
                    "doc_id": document_id,
                    "user_id": user_id,
                    "idx": i,
                    "text": chunk_text,
                    "embedding": str(embedding)
                }
            )
        conn.commit()



def get_db_engine():
    """Create a SQLAlchemy engine for direct DB access."""
    return sqlalchemy.create_engine(DB_URL)


def update_document_status(engine, document_id, status, page_count=None):
    """Update a document's status in the database."""
    with engine.connect() as conn:
        if page_count is not None:
            conn.execute(
                sqlalchemy.text(
                    "UPDATE documents SET status = :status, page_count = :page_count WHERE id = :doc_id"
                ),
                {"status": status, "page_count": page_count, "doc_id": document_id}
            )
        else:
            conn.execute(
                sqlalchemy.text(
                    "UPDATE documents SET status = :status WHERE id = :doc_id"
                ),
                {"status": status, "doc_id": document_id}
            )
        conn.commit()


def process_document(ch, method, properties, body):
    """Callback for processing a document message from RabbitMQ."""
    try:
        message = json.loads(body)
        doc_id = message.get('document_id')
        filename = message.get('filename', 'unknown')
        user_id = message.get('user_id')
        object_name = message.get('object_name')

        print(f"[Worker] Processing document: {doc_id} ({filename}) for user {user_id}")

        minio_client = get_minio_client()
        res = minio_client.get_object(BUCKET_NAME, object_name)
        pdf_bytes = res.read()
        res.close()
        print(f"[Worker] downloaded {len(pdf_bytes)} bytes from minio")

        chunks = extract_text_chunks(pdf_bytes)
        if not chunks:
            print(f"[Worker] no text found in {filename}")
            engine = get_db_engine()
            update_document_status(engine, doc_id, 'completed', page_count=0)
            engine.dispose()
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        vectors = embed_chunks(chunks)
        print(f"[Worker] generated {len(vectors)} embeddings")

        # Update status to completed
        engine = get_db_engine()
        save_chunks(engine, doc_id, user_id, chunks, vectors)
        update_document_status(engine, doc_id, 'completed', page_count=1)
        engine.dispose()

        print(f"[Worker] Completed processing: {doc_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[Worker] Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    """Connect to RabbitMQ and start consuming messages."""
    print("[Worker] Starting up...")

    # Retry connection to RabbitMQ
    connection = None
    for attempt in range(30):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            break
        except pika.exceptions.AMQPConnectionError:
            print(f"[Worker] Waiting for RabbitMQ... (attempt {attempt + 1}/30)")
            time.sleep(2)

    if connection is None:
        print("[Worker] Could not connect to RabbitMQ after 30 attempts. Exiting.")
        return

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_document)

    print(f"[Worker] Connected to RabbitMQ. Waiting for messages on '{QUEUE_NAME}'...")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print("[Worker] Shutting down.")
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == '__main__':
    main()
