def test_login_success(client):
    response = client.post(
        "/auth/login",
        json={
            "username": "admin",
            "password": "123"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
