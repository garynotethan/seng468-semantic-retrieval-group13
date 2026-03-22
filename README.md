# SENG 468: Distributed Semantic Retrieval System

A scalable semantic search engine that handles concurrent user PDF uploads and searches using natural language queries. Built using a distributed microservice architecture.

## Architecture Stack

- **API Gateway**: Flask (Python 3.12)
- **Authentication**: JWT (`Flask-JWT-Extended`)
- **Relational DB / VectorDB**: PostgreSQL + `pgvector` (User data, metadata, and embeddings)
- **Object Storage**: MinIO (Stateless PDF file storage)
- **Message Broker**: RabbitMQ (Task queue linking API and workers)
- **Background Worker**: Python (PDF chunking and embedding generation)

## Prerequisites

- Docker
- Docker Compose
- Python 3.10+ (for running the integration tests locally)

## Running the System

To deploy the entire system locally, simply pull from the root directory:

```bash
docker compose up -d --build
```

This command will automatically compile and provision the following unified services:

1. `api`: Exposes the central HTTP endpoints traversing `http://localhost:8080`.
2. `worker`: Connects to RabbitMQ for processing incoming documents asynchronously.
3. `db`: Initializes PostgreSQL for user management.
4. `rabbitmq`: Message broker for handling distributed workloads.
5. `minio`: Object storage UI natively accessible at `http://localhost:9001` (Credentials: `minioadmin`/`minioadmin`).

To view the live logs of the API and worker, use:

```bash
docker compose logs -f api
docker compose logs -f worker
```

## Running the Integration Tests

The system comes with an end-to-end integration test suite (`tests/test_api.py`) that acts as a real client HTTP requester. It intentionally requires **zero external dependencies**, utilizing only Python's built-in libraries to ensure maximum machine portability.

**Important**: Ensure the Docker containers are successfully built and currently running (`docker compose up -d`) before executing the tests.

Run the tests using standard Python `unittest`:

```bash
python3 tests/test_api.py
```

### What do the tests cover?

1. **User Signup**: Registers a new localized user and verifies PostgreSQL relational DB insertions.
2. **User Login**: Exchanges valid credentials for a JWT Token.
3. **Protected Routes**: Attempts to fetch protected user states and verifies a `401 Unauthorized` gets enforced.
4. **Document Uploads**: Emulates `multipart/form-data` payloads, pushing a mock PDF document through the API gateway natively into the MinIO remote object storage, enforcing the asynchronous `202 Accepted` architecture.
5. **Document Retrieval**: Pulls the DB relation state and verifies the system correctly retrieves the user's successfully synced MinIO files.
6. **Document Deletion**: Checks that issuing `DELETE` recursively purges the blob from MinIO alongside cleanly archiving the relational PostgreSQL DB record.

## Stopping the System

To safely stop the containers and wipe the attached volume data for a fresh run, use:

```bash
docker compose down -v
```
