"""
Manjubinha Investidor — Análises Automáticas
Usa Gemini + Google Search para encontrar e analisar documentos.
"""

import os, json, requests, time
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
WP_URL     = "https://manjubinhainvestidor.com.br"
WP_USER    = os.environ["WP_USER"]
WP_PASS    = os.environ["WP_APP_PASS"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

WP_API     = f"{WP_URL}/wp-json/wp/v2"
# WordPress.org usa Basic Auth com usuário + Application Password
import base64
_cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
WP_HEADERS = {"Authorization": f"Basic {_cred}"}

# Gemini Flash com Google Search grounding
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

# IDs de categoria serão buscados dinamicamente pelo slug
CAT_FIIS   = None  # preenchido em main()
CAT_ACOES  = None  # preenchido em main()
CONTROLE   = Path("controle_docs.json")

MES_ATUAL  = datetime.today().strftime("%B de %Y")  # ex: junho de 2026
MES_NUM    = datetime.today().strftime("%m/%Y")      # ex: 06/2026

# ── Prompt único com Google Search ────────────────────────────────────────────

PROMPT_FII = """Você é analista do site Manjubinha Investidor.

Pesquise no site oficial {ri_url} o relatório mensal ou fato relevante mais recente do FII {ticker} ({nome}), publicado em {mes}.

Com base no documento encontrado, escreva uma análise completa em HTML puro para WordPress. Use EXATAMENTE esta estrutura:

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:heading {{"level":4}} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO — PERÍODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial do fundo ({gestora}) ↗</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Tipo: {tipo} — Gestora: {gestora}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que esse fundo faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais do documento</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>DY mensal: X%</strong> — explicação.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>P/VP: X,XX</strong> — explicação.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Vacância/Liquidez: X</strong> — explicação.</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Analise se o DY está dentro do padrão ou inflado. Se fundo de papel, inclua: "⚠️ <strong>Atenção:</strong> Fundos de papel não devem ser comprados com P/VP acima de 1,0 — você pagaria mais do que a carteira de CRIs vale."</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Não + explicação direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 Conclusão em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

REGRAS: linguagem simples, máximo 600 palavras, números reais encontrados, sem markdown extra."""

PROMPT_ACAO = """Você é analista do site Manjubinha Investidor.

Pesquise no site oficial {ri_url} o resultado trimestral mais recente da empresa {ticker} ({nome}), publicado em 2026.

Com base no documento encontrado, escreva uma análise completa em HTML puro para WordPress. Use EXATAMENTE esta estrutura:

<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:heading {{"level":4}} --><h4 class="wp-block-heading"><mark style="background-color:rgba(0,0,0,0);color:#ff6900" class="has-inline-color">TIPO DO DOCUMENTO — PERÍODO</mark></h4><!-- /wp:heading -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Publicado em: DD/MM/AAAA — <a href="{ri_url}" target="_blank" rel="noreferrer noopener">Site oficial de RI ({nome}) ↗</a></p><!-- /wp:paragraph -->
<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"14px"}}}}}} --><p style="font-size:14px">Setor: {setor} — Empresa: {nome}</p><!-- /wp:paragraph --></div><!-- /wp:group -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">💬 O que essa empresa faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Receita: R$ X bi</strong> — explicação.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Lucro líquido: R$ X bi</strong> — explicação.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>DY anual: X%</strong> — explicação.</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🎯 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>O DY está dentro do padrão histórico ou inflado por extraordinários?</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA com dados reais</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Não + explicação direta.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {{"level":3}} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização: ✅/⚠️/❌ RESULTADO</strong><br>Explicação curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>📌 Conclusão em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

REGRAS: linguagem simples, máximo 600 palavras, números reais encontrados, sem markdown extra."""

# ── Helpers ────────────────────────────────────────────────────────────────────
def carregar(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default

def salvar(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def gemini_search(prompt):
    """Chama Gemini Flash com pausa para respeitar rate limit (15 RPM)."""
    time.sleep(5)  # max 12 req/min, abaixo do limite de 15 RPM
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }
    for tentativa in range(3):
        r = requests.post(GEMINI_URL, json=payload, timeout=90)
        if r.status_code == 200:
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts)
        elif r.status_code == 429:
            print(f"  ⏳ Rate limit — aguardando 60s... (tentativa {tentativa+1}/3)")
            time.sleep(60)
        else:
            print(f"  ❌ Gemini {r.status_code}: {r.text[:200]}")
            return None
    print("  ❌ Gemini: 3 tentativas falharam.")
    return None

def get_or_create_category(slug, name):
    """Busca categoria pelo slug ou cria se não existir."""
    r = requests.get(f"{WP_API}/categories", headers=WP_HEADERS, params={"slug": slug})
    cats = r.json()
    if isinstance(cats, list) and cats:
        return cats[0]["id"]
    # Cria a categoria
    r = requests.post(f"{WP_API}/categories", headers=WP_HEADERS, json={"name": name, "slug": slug})
    return r.json().get("id")

def get_tag(ticker):
    r = requests.get(f"{WP_API}/tags", params={"search": ticker}, headers=WP_HEADERS)
    tags = r.json()
    if isinstance(tags, list) and tags:
        return tags[0]["id"]
    nova = requests.post(f"{WP_API}/tags", json={"name": ticker}, headers=WP_HEADERS).json()
    return nova.get("id")

def publicar(titulo, conteudo, categoria, ticker):
    tag_id = get_tag(ticker)
    r = requests.post(f"{WP_API}/posts", headers=WP_HEADERS, json={
        "title": titulo,
        "content": conteudo,
        "status": "publish",
        "categories": [categoria],
        "tags": [tag_id] if tag_id else []
    })
    if r.status_code in (200, 201):
        url = r.json()["link"]
        print(f"  ✅ {url}")
        return url
    print(f"  ❌ WP {r.status_code}: {r.text[:300]}")
    return None

def atualizar_ranking(ticker, url, tipo):
    ranking = carregar("ranking.json", {})
    lista = ranking.get("fiis" if tipo == "fii" else "acoes", [])
    for item in lista:
        if item["ticker"] == ticker:
            item["post_url"] = url
            break
    ranking["ultima_atualizacao"] = datetime.today().strftime("%Y-%m-%d")
    salvar("ranking.json", ranking)

# ── Processamento ──────────────────────────────────────────────────────────────
def processar(lista, controle, mes, tipo):
    label = "FIIs" if tipo == "fii" else "Ações"
    print(f"\n{'📦' if tipo=='fii' else '📈'} {label}...")

    for ativo in lista:
        t = ativo["ticker"]
        # Chave de controle por mês — gera 1 análise por mês por ativo
        key = f"{t}_{mes}"
        if key in controle:
            print(f"  → {t}: já analisado este mês.")
            continue

        print(f"\n  → {t} ({ativo['nome']})")
        print(f"     🔍 Buscando e analisando com Gemini...")

        if tipo == "fii":
            prompt = PROMPT_FII.format(
                ticker=t, nome=ativo["nome"],
                ri_url=ativo["ri_url"], tipo=ativo.get("tipo", ""),
                gestora=ativo.get("gestora", ""), mes=mes
            )
        else:
            prompt = PROMPT_ACAO.format(
                ticker=t, nome=ativo["nome"],
                ri_url=ativo["ri_url"], setor=ativo.get("setor", ""),
                mes=mes
            )

        analise = gemini_search(prompt)
        if not analise:
            controle[key] = {"status": "erro_gemini"}
            salvar(CONTROLE, controle)
            continue

        # Extrai título do documento da análise
        titulo = f"{t} — {ativo['nome']} | {mes}"
        cat = CAT_FIIS if tipo == "fii" else CAT_ACOES
        print(f"     📝 Publicando...")
        url = publicar(titulo, analise, cat, t)

        if url:
            atualizar_ranking(t, url, tipo)
            controle[key] = {"status": "ok", "url": url}
        else:
            controle[key] = {"status": "erro_wp"}

        salvar(CONTROLE, controle)

def main():
    print(f"🐟 Manjubinha — {datetime.today().strftime('%Y-%m-%d %H:%M UTC')}")
    config   = carregar("config.json", {})
    controle = carregar(CONTROLE, {})

    # Busca/cria categorias no WordPress.org
    global CAT_FIIS, CAT_ACOES
    CAT_FIIS  = get_or_create_category("analises-fiis", "FIIs | Análises")
    CAT_ACOES = get_or_create_category("documentos-acoes", "Ações | Análises")
    print(f"   📂 Categoria FIIs: {CAT_FIIS} | Ações: {CAT_ACOES}")
    mes      = datetime.today().strftime("%m-%Y")  # ex: 06-2026

    print(f"   📅 Mês: {MES_ATUAL}")

    processar(config.get("fiis", []),  controle, mes, "fii")
    processar(config.get("acoes", []), controle, mes, "acao")
    print("\n✅ Concluído!")

if __name__ == "__main__":
    main()
