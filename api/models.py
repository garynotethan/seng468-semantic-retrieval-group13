from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from pgvector.sqlalchemy import Vector

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Document(db.Model):
    __tablename__ = 'documents'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    status = db.Column(db.String(50), nullable=False, default='processing')
    page_count = db.Column(db.Integer, nullable=True)

class DocumentChunk(db.Model):
    # stores the chunks for the documents
    __tablename__ = 'document_chunks'

    id = db.Column(db.String(36), primary_key=True)
    document_id = db.Column(db.String(36), db.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    # cascade for proper deletion 
    user_id = db.Column(db.Integer, nullable=False) 
    chunk_index = db.Column(db.Integer, nullable=True)
    chunk_text = db.Column(db.Text, nullable=True)
    embedding = db.Column(Vector(384))

     
