import requests

TIMEOUT = 10
MAX_RESPONSE_SECONDS = 0.3  # нарочно жёсткий порог: проверка будет нестабильной


def test_user_response_is_fast(base_url):
    response = requests.get(f"{base_url}/users/1", timeout=TIMEOUT)

    assert response.status_code == 200
    assert response.elapsed.total_seconds() < MAX_RESPONSE_SECONDS