import os
import uuid
import time
import json as json_lib
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import pika
from models import db, User, Document
import storage
import pika
import shared
import sqlalchemy 
import sys
sys.path.insert(0, '/app')
from shared.embeddings import embed_text

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
QUEUE_NAME = 'document_processing'

def publish_to_queue(message: dict):
    """Publish a message to the document_processing queue."""
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST,
                                     connection_attempts=3,
                                     retry_delay=2)
        )
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=json_lib.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # persistent
        )
        connection.close()
    except Exception as e:
        print(f"Warning: Could not publish to RabbitMQ: {e}")

app = Flask(__name__)

# Basic Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/seng468')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret-key-change-in-prod')

db.init_app(app)
jwt = JWTManager(app)

with app.app_context():
    retries = 5
    while retries > 0:
        try:
            db.session.execute(text("CREAT EXTENSION IF NOT EXISTS vector"))
            db.session.commit()

            db.create_all()
            storage.init_bucket()
            print("Database and MinIO connected successfully.")
            break
        except Exception as e:
            print(f"Waiting for services to be ready... ({retries} retries left): {e}")
            retries -= 1
            time.sleep(2)
    else:
        print("Could not connect to database/minio after multiple retries.")


@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Missing username or password"}), 400
        
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"error": "Username already exists"}), 409
        
    new_user = User(username=data['username'])
    new_user.set_password(data['password'])
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({"message": "User created successfully", "user_id": str(new_user.id)}), 200

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"error": "Missing username or password"}), 400
        
    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({"error": "Invalid credentials"}), 401
        
    access_token = create_access_token(identity=str(user.id))
    return jsonify({"token": access_token, "user_id": str(user.id)}), 200

@app.route('/documents', methods=['POST'])
@jwt_required()
def upload_document():
    user_id_str = get_jwt_identity()
    user_id = int(user_id_str)
    
    if 'file' not in request.files:
        return jsonify({"error": "No file parameter"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    # Generate UUID and object path
    doc_id = str(uuid.uuid4())
    object_name = f"{user_id}/{doc_id}.pdf"
    
    # Calculate file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    
    # Save to MinIO
    storage.upload_file(file, object_name, file_length)
    
    # Record metadata in Postgres
    new_doc = Document(
        id=doc_id,
        user_id=user_id,
        filename=file.filename,
        status='processing'
    )
    db.session.add(new_doc)
    db.session.commit()

    # Publish processing task to RabbitMQ
    publish_to_queue({
        "document_id": doc_id,
        "user_id": user_id,
        "filename": file.filename,
        "object_name": object_name
    })

    return jsonify({
        "message": "PDF uploaded, processing started",
        "document_id": doc_id,
        "status": "processing"   
    }), 202

@app.route('/documents', methods=['GET'])
@jwt_required()
def list_documents():
    user_id = int(get_jwt_identity())
    docs = Document.query.filter_by(user_id=user_id).all()
    results = []
    for doc in docs:
        results.append({
            "document_id": doc.id,
            "filename": doc.filename,
            "upload_date": doc.upload_date.isoformat() + "Z",
            "status": doc.status,
            "page_count": doc.page_count
        })
    return jsonify(results), 200

@app.route('/documents/<id>', methods=['DELETE'])
@jwt_required()
def delete_document(id):
    user_id = int(get_jwt_identity())
    doc = Document.query.filter_by(id=id, user_id=user_id).first()
    
    if not doc:
        return jsonify({"error": "Document not found or not owned by user"}), 404
        
    # Remove from MinIO
    object_name = f"{user_id}/{doc.id}.pdf"
    storage.delete_file(object_name)
    
    # Remove from Postgres
    db.session.delete(doc)
    db.session.commit()
    
    return jsonify({
        "message": "Document and all associated data deleted",
        "document_id": id
    }), 200

@app.route('/search', methods=['GET'])
@jwt_required()
def search():
    user_id = int(get_jwt_identity())
    query = request.args.get('q', '').strip().lower()

    query_vector = embed_text(query)

    results = db.session.execute(
        sqlalchemy.text(
            '''
            SELECT dc.document_id, dc.chunk_text, dc.chunk_index, d.filename,
            1 - (dc.embeddiong <=> CAST(:query_vec AS vector)) AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.user_id = :user_id
            ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
            LIMIT 5
            '''
        ),
        {
            "query_vec": str(query_vector),
            "user_id": user_id
        }
    ).fetchall()

    output = []
    for row in results:
        output.append({
            "chunk_text": row.chunk_text,
            "score": row.score,
            "document_id": row.id,
            "filename": row.filename,
        })

    return jsonify(output), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8080)
