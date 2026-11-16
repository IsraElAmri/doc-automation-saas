import urllib.request, uuid, os, json

def upload_file(token, filepath):
    filename = os.path.basename(filepath)
    boundary = uuid.uuid4().hex
    
    with open(filepath, 'rb') as f:
        file_bytes = f.read()

    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'
    ).encode('utf-8') + file_bytes + f'\r\n--{boundary}--\r\n'.encode('utf-8')

    req = urllib.request.Request(
        'http://127.0.0.1:8000/upload',
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': f'multipart/form-data; boundary={boundary}'
        }
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        print(f"Uploaded {filename}: ID={res.get('document_id')}, Category={res.get('category')}")

data = json.dumps({'email': 'demo_user@itgate.tn', 'password': 'Password123!'}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/auth/login', data=data, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r:
    token = json.loads(r.read().decode())['access_token']

files = [
    r'sample_test_files\ocr_invoice_receipt.png',
    r'sample_test_files\q3_financial_report.txt',
    r'sample_test_files\ocr_invoice_receipt.jpg',
    r'sample_test_files\sales_data.csv',
]

for fp in files:
    upload_file(token, fp)
