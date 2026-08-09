import requests

BASE_URL = "http://127.0.0.1:8000"

def test_upload_txt():
    with open("random_yap.txt", "w", encoding="utf-8") as f:
        f.write("This is a test document for the upload route.")

    with open("random_yap.txt", "rb") as f:
        response = requests.post(
            f"{BASE_URL}/ingest/upload",
            files={"file": ("random_yap.txt", f, "text/plain")},
            data={"notebook_id": "fake-notebook-id"},
        )

    print(response.status_code)
    print(response.json())
    assert response.status_code == 200
    assert "document_id" in response.json()
    print("Upload test OK")

def test_upload_wrong_extension():
    with open("random_yap.pdf", "w") as f:
        f.write("not a real pdf")

    with open("random_yap.pdf", "rb") as f:
        response = requests.post(
            f"{BASE_URL}/ingest/upload",
            files={"file": ("random_yap.pdf", f, "application/pdf")},
            data={"notebook_id": "fake-notebook-id"},
        )

    print(response.status_code)
    print(response.json())
    assert response.status_code == 400
    print("Wrong extension test OK")

if __name__ == "__main__":
    test_upload_txt()
    test_upload_wrong_extension()