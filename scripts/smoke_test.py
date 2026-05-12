import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def get(path: str):
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=5) as response:
        body = response.read().decode("utf-8")
        return response.status, body


def main() -> None:
    health_status, health_body = get("/health")
    marks_status, marks_body = get("/marks/api")

    print("Health:", health_status, health_body)
    print("Marks API:", marks_status)
    try:
        print(json.dumps(json.loads(marks_body), indent=2))
    except json.JSONDecodeError:
        print(marks_body[:500])

    assert health_status == 200
    assert marks_status == 200
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
