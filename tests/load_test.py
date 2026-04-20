import time
import uuid
import io
from locust import HttpUser, task, between

class SemanticSearchUser(HttpUser):
    wait_time = between(1, 3)
    token = None
    user_id = None
    username = f"loadtest_{uuid.uuid4().hex[:8]}"

    def on_start(self):
        """Signup and login once when the user starts."""
        signup_data = {
            "username": self.username,
            "password": "password123"
        }
        # Signup
        self.client.post("/auth/signup", json=signup_data)
        
        # Login
        response = self.client.post("/auth/login", json=signup_data)
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("token")
            self.user_id = data.get("user_id")

    @task(1)
    def upload_document(self):
        """Upload a dummy PDF document."""
        if not self.token:
            return
            
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        # Simple dummy PDF content structure
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Title (Test) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        headers = {"Authorization": f"Bearer {self.token}"}
        
        with self.client.post("/documents", files=files, headers=headers, catch_response=True) as response:
            if response.status_code == 202:
                response.success()
            else:
                response.failure(f"Upload failed with status {response.status_code}")

    @task(5)
    def search_documents(self):
        """Perform a semantic search query."""
        if not self.token:
            return
            
        headers = {"Authorization": f"Bearer {self.token}"}
        query = "machine learning optimization"
        
        with self.client.get(f"/search?q={query}", headers=headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Search failed with status {response.status_code}")

    @task(2)
    def list_documents(self):
        """List documents for the user."""
        if not self.token:
            return
            
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.get("/documents", headers=headers)
