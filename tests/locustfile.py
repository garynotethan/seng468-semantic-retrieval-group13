from locust import HttpUser, task, between, events
import os
import time
import random
 

class SearchUser(HttpUser):

    wait_time = between(1, 5)

    def on_start(self):
        self.username = f"loadtest_{id(self)}_{time.time()}"
        self.password = "test"
        self.token = None
        self.doc_ids = []
        
        signup = self.client.post("/auth/signup", json = {
            "username": self.username,
            "password": self.password
            })

        login = self.client.post("/auth/login", json = {
            "username": self.username,
            "password": self.password
            })

        if login.status_code == 200:
            self.token = login.json().get("token")
        else:
            print(f"error during login for {self.username}: {login.status_code}")
        
        def _auth_headers(self):
            return {"Authorization": f"Bearer {self.token}"} if self.token else {}


    @task(3)
    def search_documents(self):
        
    

    @task(2)
    def list_documents(self):
        pass
    

    @task(1)
    def upload_document(self):
        DOCUMENTS = [
            os.path.join(os.path.dirname(__file__), "test_documents", "small.pdf"),
            os.path.join(os.path.dirname(__file__), "test_documents", "arabic.pdf"),
            os.path.join(os.path.dirname(__file__), "test_documents", "medium.pdf"),
            os.path.join(os.path.dirname(__file__), "test_documents", "multicolumn.pdf"),
        ]
        pdf_path = random.choice(DOCUMENTS)

        with open(pdf_path, "rb") as f:
            response = self.client.post(
                "/documents",
                files = {"file": (os.path.basename(pdf_path), f, "applications/pdf")},
                headers = self.auth_headers(),
                name = "small document"
            )
            if response.status_code == 202:
                doc_id = response.json().get("document_id")
                if doc_id:
                    self.doc_ids.append(doc_id)
    @task(0)
    def upload_large_document(self):
        pdf_path = os.path.join(os.path.dirname(__file__), "test_documents", "large.pdf")
        with open(pdf_path, "rb") as f:
            response = self.client.post(
                "/documents",
                files = {"file": ("large.pdf", f, "applications/pdf")},
                headers = self.auth_headers(),
                name = "large document"
            )
            if response.status_code == 202:
                    doc_id = response.json().get("document_id")
                    if doc_id:
                        self.doc_ids.append(doc_id)

    upload_large_document.locust_tag_set = {"large"}
    # locust --tags large to run

    

