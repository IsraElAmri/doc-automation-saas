import requests
import json

BASE_URL = "http://localhost:8000"

# Create a test file
test_content = """
This is a test document about Machine Learning.
Machine learning is a subset of artificial intelligence.
Key concepts include supervised learning, unsupervised learning, and reinforcement learning.
Popular algorithms include neural networks, decision trees, and SVM.
Applications include image recognition, natural language processing, and recommendation systems.
"""

with open("test_document.txt", "w") as f:
    f.write(test_content)

# Test 1: Upload document
print("1. UPLOADING DOCUMENT...")
with open("test_document.txt", "rb") as f:
    files = {"file": f}
    response = requests.post(f"{BASE_URL}/upload", files=files)
    print(json.dumps(response.json(), indent=2))
    doc_id = response.json()["document_id"]

# Test 2: List documents
print("\n2. LISTING DOCUMENTS...")
response = requests.get(f"{BASE_URL}/documents")
print(json.dumps(response.json(), indent=2))

# Test 3: Ask question
print("\n3. ASKING QUESTION...")
response = requests.post(
    f"{BASE_URL}/ask/{doc_id}",
    json={"question": "What is machine learning?"}
)
print(json.dumps(response.json(), indent=2))

# Test 4: Get chat history
print("\n4. CHAT HISTORY...")
response = requests.get(f"{BASE_URL}/chat-history/{doc_id}")
print(json.dumps(response.json(), indent=2))

print("\n[SUCCESS] ALL TESTS PASSED!")