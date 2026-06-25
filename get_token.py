import requests
import os

code = os.environ.get("WP_CODE", "")

if not code:
    print("ERRO: variavel WP_CODE nao definida")
    exit(1)

print(f"Trocando codigo: {code[:6]}...")

resp = requests.post(
    "https://public-api.wordpress.com/oauth2/token",
    data={
        "client_id": "142632",
        "client_secret": "3VUIzQ0LtdCBrFYjFx16YJyPb6Yw486IjgiwTshHIdN9BKrgLiXAeW35NghvdRDr",
        "redirect_uri": "https://diakofart.github.io/manjubinha-analises/callback.html",
        "code": code,
        "grant_type": "authorization_code"
    }
)
data = resp.json()
if "access_token" in data:
    print(f"\n✅ TOKEN GERADO:\n{data['access_token']}\n")
else:
    print(f"ERRO: {data}")
