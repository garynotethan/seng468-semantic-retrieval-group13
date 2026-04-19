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
        queries = [
            "continuous functions and metric spaces",
            "topological spaces and open sets",
            "convergence of sequences",
            "homeomorphism between spaces",
            "compact subsets of a metric space",
            "definition of a manifold",
            "boundary of a topological space",
            "connected components",
        ]
        query = random.choice(queries)
        self.client.get(
            f"/search?q={query}",
            headers=self._auth_headers(),
            name="/search?=[query]"
        )
    

    @task(2)
    def list_documents(self):
        self.client.get("/documents", headers=self._auth_headers())
    

    @task(1)
    def upload_document(self):
        pdf_path = os.path.join(os.path.dirname(__file__), "test_documents", "large.pdf")

        with open(pdf_path, "rb") as f:
            response = self.client.post(
                "/documents",
                files = {"file": ("large.pdf", f, "application/pdf")},
                headers = self._auth_headers(),
                name = "/documents [upload 5MB]"
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
                files = {"file": ("large.pdf", f, "application/pdf")},
                headers = self._auth_headers(),
                name = "large document"
            )
            if response.status_code == 202:
                    doc_id = response.json().get("document_id")
                    if doc_id:
                        self.doc_ids.append(doc_id)

    upload_large_document.locust_tag_set = {"large"}
    # locust --tags large to run



