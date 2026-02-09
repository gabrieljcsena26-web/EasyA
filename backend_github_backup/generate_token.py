from app.core.security import create_access_token

if __name__ == "__main__":
    payload = {
        "slug": "clinica123",   # TEM que existir no config.json
        "role": "admin"
    }

    token = create_access_token(payload)
    print("\nTOKEN JWT (Postman):\n")
    print(token)
