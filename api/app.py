import os
import uuid
import time
from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from models import db, User, Document
import storage

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

    # send to rabbitmq
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='pdf_tasks_queue', durable=True)
    message = {
        "document_id" : doc_id,
        "user_id" : user_id
    }
    channel.basic_publish(
            exchange = '',
            routing_key=pdf_tasks_queue,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistant)
    )
    
    
    
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
    query = request.args.get('q', '')
    return jsonify([]), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8080)
