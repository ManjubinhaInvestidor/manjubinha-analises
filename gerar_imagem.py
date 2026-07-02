import base64
import json
import os
import sys
import urllib.request

key = os.environ["GEMINI_API_KEY"]
prompt = os.environ["PROMPT"]
outfile = os.environ.get("OUTFILE", "imagem.png")


def chamar(model, body):
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


tentativas = [
    ("gemini-2.5-flash-image", {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "3:2"}},
    }),
    ("gemini-2.5-flash-image", {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }),
    ("gemini-2.0-flash-preview-image-generation", {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }),
]

resp = None
for model, body in tentativas:
    try:
        resp = chamar(model, body)
        break
    except Exception as e:
        print("falhou %s: %s" % (model, e))

if resp is None:
    print("nenhum modelo de imagem disponivel")
    sys.exit(1)

for cand in resp.get("candidates", []):
    for part in cand.get("content", {}).get("parts", []):
        if "inlineData" in part:
            os.makedirs("imagens", exist_ok=True)
            caminho = os.path.join("imagens", outfile)
            with open(caminho, "wb") as f:
                f.write(base64.b64decode(part["inlineData"]["data"]))
            print("salvo", caminho)
            sys.exit(0)

print("sem imagem na resposta")
print(json.dumps(resp)[:800])
sys.exit(1)
