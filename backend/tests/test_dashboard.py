def get_token(client):
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "123"}
    )
    return response.json()["token"]


def test_listar_clientes(client):
    token = get_token(client)

    response = client.get(
        "/dashboard/clientes",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert isinstance(body["data"], list)
