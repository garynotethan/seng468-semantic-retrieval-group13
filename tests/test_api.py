import unittest
import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://localhost:8080"
TEST_USER = "testuser_" + str(int(time.time()))

class TestAPIAuth(unittest.TestCase):
    token = None
    doc_id = None

    @classmethod
    def get_token(cls):
        if cls.token:
            return cls.token
        data = json.dumps({"username": TEST_USER, "password": "password"}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/auth/signup", data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                pass
        except urllib.error.HTTPError as e:
            e.close()
        except Exception:
            pass
            
        req = urllib.request.Request(f"{BASE_URL}/auth/login", data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            res_body = json.loads(response.read().decode())
            cls.token = res_body["token"]
        return cls.token

    def test_1_signup(self):
        user = "new_" + TEST_USER
        data = json.dumps({"username": user, "password": "password"}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/auth/signup", data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)

    def test_2_login(self):
        token = self.get_token()
        self.assertIsNotNone(token)

    def test_3_protected_route_fails_without_token(self):
        req = urllib.request.Request(f"{BASE_URL}/documents")
        try:
            with urllib.request.urlopen(req) as response:
                self.fail("Should have thrown 401 Unauthorized")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)
            e.close()

    def test_4_upload_document(self):
        token = self.get_token()
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"test.pdf\"\r\n"
            f"Content-Type: application/pdf\r\n\r\n"
            f"dummy pdf content\r\n"
            f"--{boundary}--\r\n"
        ).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/documents", data=body)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 202)
            res_body = json.loads(response.read().decode())
            self.__class__.doc_id = res_body.get("document_id")
            self.assertIsNotNone(self.__class__.doc_id)

    def test_5_list_documents(self):
        token = self.get_token()
        req = urllib.request.Request(f"{BASE_URL}/documents")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            res_body = json.loads(response.read().decode())
            self.assertIsInstance(res_body, list)

    def test_6_delete_document(self):
        token = self.get_token()
        doc_id = self.__class__.doc_id
        if not doc_id:
            self.skipTest("No document ID from upload test")
        
        req = urllib.request.Request(f"{BASE_URL}/documents/{doc_id}", method="DELETE")
        req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)

if __name__ == '__main__':
    unittest.main()
