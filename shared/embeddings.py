from sentence_transformers import SentenceTransformer

model = None

def get_model():
    global model
    if model is None:
        model = SentenceTransformer("all-MiniLM-L6-v2")
    return model


def embed_text(text: str) -> list:
    model = get_model()
    # lowkey the best balance between speed and performance. 
    # may consider L12 if we need a lil bit more extra accurate
    embedding = model.encode(text).tolist()

    return embedding
    

def embed_chunks(chunks: list[str]) -> list:
    model = get_model()
    return model.encode(chunks).tolist()
