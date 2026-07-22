"""Reindexa no Google (Indexing API, URL_UPDATED) as paginas com titulo reescrito."""
import os, json, requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

GOOGLE_INDEXING_KEY = os.environ.get("GOOGLE_INDEXING_KEY", "")
SITE = "https://manjubinhainvestidor.com.br"
WP_API = f"{SITE}/wp-json/wp/v2"

IDS = [1204,1473,653,1447,1085,1472,1202,1067,1088,716,911,1065,509,652,539,665,1197,549,1199,1087]

def get_url(pid):
    try:
        r = requests.get(f"{WP_API}/posts/{pid}", params={"_fields": "slug"}, timeout=30)
        slug = r.json().get("slug")
        if slug:
            return f"{SITE}/{slug}/"
    except Exception as e:
        print(f"  erro slug {pid}: {e}")
    return None

def solicitar_indexacao(url, creds):
    creds.refresh(GoogleAuthRequest())
    r = requests.post(
        "https://indexing.googleapis.com/v3/urlNotifications:publish",
        headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
        json={"url": url, "type": "URL_UPDATED"},
        timeout=30,
    )
    print(f"  {r.status_code} {url}")
    if r.status_code != 200:
        print(f"    {r.text[:200]}")

def main():
    if not GOOGLE_INDEXING_KEY:
        print("Sem GOOGLE_INDEXING_KEY"); return
    creds_info = json.loads(GOOGLE_INDEXING_KEY)
    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/indexing"]
    )
    ok = 0
    for pid in IDS:
        url = get_url(pid)
        if url:
            solicitar_indexacao(url, creds)
            ok += 1
    print(f"Feito: {ok}/{len(IDS)}")

if __name__ == "__main__":
    main()
