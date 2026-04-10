from locust import HttpUser, task, between, events
import os
import time

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


    @task()
    def search_documents(self):
        pass
    

    @task()
    def list_documents(self):
        pass
    

    @task()
    def upload_document(self):
        pass