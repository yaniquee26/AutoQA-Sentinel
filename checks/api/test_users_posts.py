import pytest
import requests

TIMEOUT = 10


def test_get_user_returns_200_and_fields(base_url):
    response = requests.get(f"{base_url}/users/1", timeout=TIMEOUT)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["id"], int)
    assert isinstance(data["name"], str)
    assert isinstance(data["email"], str)


@pytest.mark.parametrize("user_id", [1, 2, 10])
def test_get_existing_users(base_url, user_id):
    response = requests.get(f"{base_url}/users/{user_id}", timeout=TIMEOUT)

    assert response.status_code == 200
    assert response.json()["id"] == user_id


def test_get_missing_user_returns_404(base_url):
    response = requests.get(f"{base_url}/users/9999", timeout=TIMEOUT)

    assert response.status_code == 404
    assert response.json() == {}


def test_create_post_returns_201(base_url):
    payload = {"title": "test", "body": "hello", "userId": 1}

    response = requests.post(f"{base_url}/posts", json=payload, timeout=TIMEOUT)

    assert response.status_code == 201
    data = response.json()
    assert isinstance(data["id"], int)
    assert data["title"] == payload["title"]
    assert data["body"] == payload["body"]
    assert data["userId"] == payload["userId"]