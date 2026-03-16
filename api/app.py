from flask import Flask, request

app = Flask(__name__)

@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()

    username = data.get('username')
    # todo: check if user exists, 409 if yes
    password = data.get('password')

    # todo: return real uuid
    return {
        "message": "User created successfully",
        "user_id": "uuid-or-integer"   
    }, 200

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()

    username = data.get('username')
    password = data.get('password')
    # todo: check if pass matches user, 401

    # todo: return real auth token, uuid
    return {
        "token": "real token here",
        "user_id": "uuid-or-integer"   
    }, 200

@app.route('/documents', methods=['POST'])
def upload_document():
    #todo: require auth?
    pdf_file = request.files['file']
    # upload... 
    return {
        "message": "PDF uploaded, processing started",
        "document_id": "uuid-123",
        "status": "processing"   
    }, 202

@app.route('/documents', methods=['GET'])
def list_documents():
    #todo: this
    return [
        {
        "document_id": "uuid-123",
        "filename": "research_paper.pdf",
        "upload_date": "2026-03-15t10:30:00z",
        "status": "ready",
        "page_count": 12
        },
        {
        "document_id": "uuid-456",
        "filename": "textbook_chapter.pdf",
        "upload_date": "2026-03-16t14:22:00z",
        "status": "processing",
        "page_count": None
        }
    ], 200

@app.route('/documents/<id>', methods=['DELETE'])
def delete_document(id):
    #todo: require auth, delete, 404 if not found/other user
    return {
        "message": "Document and all associated data deleted",
        "document_id": "uuid-123"
    }, 200

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '')
    # return 5 max 
    return [

    ], 200



if __name__ == '__main__':
    app.run(debug=True, port=8080)