"""
Manjubinha Investidor - Analises Automaticas
Roda 4x por dia (a cada 6h). Processa 2 FIIs + 2 Acoes por rodada.
Carrossel continuo: publica o doc mais recente de cada ativo via Investidor10.
Controle por ID do documento - nunca repete o mesmo doc.
"""

import os, json, requests, time, re
# --- Forca IPv4: runners do GitHub Actions nao tem rota IPv6; o site tem registro AAAA ---
import socket
import urllib3.util.connection as _u3
_u3.allowed_gai_family = lambda: socket.AF_INET
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

# Config
WP_URL    = "https://manjubinhainvestidor.com.br"
WP_USER   = os.environ["WP_USER"]
WP_PASS   = os.environ["WP_APP_PASS"]
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
GOOGLE_INDEXING_KEY = os.environ.get("GOOGLE_INDEXING_KEY", "")

WP_API = f"{WP_URL}/wp-json/wp/v2"
import base64
# --- Retentativas automaticas para instabilidade de rede (nao retenta 429) ---
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
_retry = Retry(total=2, connect=2, read=2, backoff_factor=10, status_forcelist=[500, 502, 503, 504], allowed_methods=None, respect_retry_after_header=False)
_sessao = requests.Session()
_sessao.mount("https://", HTTPAdapter(max_retries=_retry))
_sessao.mount("http://", HTTPAdapter(max_retries=_retry))
requests = _sessao
_cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
WP_HEADERS = {"Authorization": f"Basic {_cred}"}

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"

CONFIG     = Path("config.json")
CONTROLE   = Path("controle_docs.json")
POR_RODADA = 2  # 2 FIIs + 2 Acoes = 4 por rodada

INV10_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Manjubinha/1.0)"}

PROMPT_FII = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes do FII {ticker} ({nome}) com base no documento: {descricao_doc}{data_sufixo} (link: {url_doc}).

IMPORTANTE - FOCO DO POST:
O DOCUMENTO e o protagonista deste post. As secoes Pontos de Atencao, Deve Ser Acompanhado, Boa Noticia e Mudou fundamento devem PARTIR do que o documento traz e so entao conectar com o contexto do FII. A secao "O que esse fundo faz" e apenas uma introducao curta de no maximo 2-3 frases. Nao escreva um post sobre o FII em geral: escreva um post sobre ESTE documento.

Escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:html -->
<div style="background:linear-gradient(145deg,#171717,#262626);border-radius:14px;padding:20px;display:flex;gap:16px;align-items:center">
<div>{logo_html}</div>
<div style="color:#e5e5e5">
<h4 style="margin:0 0 8px 0"><mark style="background-color:rgba(0,0,0,0);color:#f6c453" class="has-inline-color">{descricao_doc}{data_titulo}</mark></h4>
<p style="font-size:14px;margin:0 0 4px 0;color:#e5e5e5">{publicado_em}<a href="{url_doc}" target="_blank" rel="noreferrer noopener" style="color:#f6c453">Documento oficial ({gestora})</a></p>
<p style="font-size:14px;margin:0;color:#e5e5e5">Tipo: {tipo} - Gestora: {gestora}</p>
</div>
</div>
<!-- /wp:html -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📄 O que o documento diz</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>1 frase explicando o que E esse tipo de documento e por que ele e publicado (ex.: o que e um regimento interno, um comunicado ao mercado, um relatorio gerencial).</p><!-- /wp:paragraph -->
<!-- wp:list --><ul class="wp-block-list"><li>Ponto REAL do conteudo do documento.</li><li>Segundo ponto REAL do documento.</li><li>Terceiro ponto REAL do documento.</li></ul><!-- /wp:list -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💬 O que esse fundo faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Introducao curta de no maximo 2-3 frases, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:table --><figure class="wp-block-table"><table><thead><tr><th>Indicador</th><th>Valor</th><th>Leitura</th></tr></thead><tbody><tr><td>DY mensal</td><td>X%</td><td>✅ ou ⚠️ + 2-4 palavras</td></tr><tr><td>P/VP</td><td>X,XX</td><td>✅ ou ⚠️ + 2-4 palavras</td></tr></tbody></table></figure><!-- /wp:table -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💰 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Analise se o DY esta dentro do padrao. Se fundo de papel: Fundos de papel nao devem ser comprados com P/VP acima de 1,0.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Partindo do que o DOCUMENTO traz, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Partindo do que o DOCUMENTO traz, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Partindo do que o DOCUMENTO traz, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Nao com explicacao direta, partindo do documento.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda:</strong> SELO<br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização:</strong> SELO<br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>Conclusao em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🐟 O que isso significa pra você</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA 2 a 3 frases no tom do Manjubinha (um peixinho iniciante que aprende junto), explicando de forma pratica o que esta analise significa para o pequeno investidor. Nao e recomendacao de compra ou venda.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">❓ Perguntas rápidas</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Pergunta real e comum sobre este FII?</strong><br>Resposta curta e direta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Segunda pergunta real sobre este FII?</strong><br>Resposta curta e direta.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🔗 Leia também</h3><!-- /wp:heading -->
<!-- wp:list --><ul class="wp-block-list"><li><a href="https://manjubinhainvestidor.com.br/fiis-tijolo-vs-papel/">FIIs de Tijolo vs FIIs de Papel: qual a diferença</a></li><li><a href="https://manjubinhainvestidor.com.br/fiis-vs-acoes/">FIIs vs Ações: renda, riscos e como analisar</a></li></ul><!-- /wp:list -->

Regras:
- Linguagem simples e acolhedora para iniciantes. Use acentuacao e ortografia corretas do portugues (ç, ã, õ, é, í, ó, ê).
- Na secao "O que o documento diz": use os 3 bullets para o conteudo REAL do documento. Se o documento nao trouxer informacao relevante para o cotista, diga isso com transparencia em 1 bullet (ex.: "comunicado operacional, sem impacto para o cotista") e NUNCA invente conteudo.
- Na secao "Merece Aporte?", substitua a palavra SELO por EXATAMENTE um destes tres selos coloridos, conforme sua conclusao:
  COMPRAR -> <span style="background:#23c55e;color:#0a1118;padding:2px 12px;border-radius:12px;font-weight:700">COMPRAR</span>
  ACOMPANHAR -> <span style="background:#f6c453;color:#0a1118;padding:2px 12px;border-radius:12px;font-weight:700">ACOMPANHAR</span>
  EVITAR -> <span style="background:#525252;color:#fff;padding:2px 12px;border-radius:12px;font-weight:700">EVITAR</span>
- Na tabela de Indicadores, a coluna Leitura deve ser ✅ ou ⚠️ seguido de 2 a 4 palavras.
- Cada numero importante deve ganhar uma frase curta "isso importa porque..." conectando o dado ao bolso do investidor.
- NUNCA imprima "Data nao disponivel"; se faltar alguma data, simplesmente omita a mencao.
- TODO termo tecnico usado no post (DY, P/VP, CRI, vacancia, carencia de juros, waiver, TTM, alavancagem, tag along, etc.) deve ser explicado entre parenteses na PRIMEIRA vez em que aparecer no texto. Explique apenas os termos que voce realmente usa; nao explique termos que nao aparecem.
- Mantenha os links da secao Leia tambem exatamente como estao no modelo.
- Maximo 950 palavras. Numeros reais, nunca invente dados. Sem markdown extra."""

PROMPT_ACAO = """Voce e analista do site Manjubinha Investidor. Pesquise informacoes recentes da empresa {ticker} ({nome}) com base no documento: {descricao_doc}{data_sufixo} (link: {url_doc}).

IMPORTANTE - FOCO DO POST:
O DOCUMENTO e o protagonista deste post. As secoes Pontos de Atencao, Deve Ser Acompanhado, Boa Noticia e Mudou fundamento devem PARTIR do que o documento traz e so entao conectar com o contexto da empresa. A secao "O que essa empresa faz" e apenas uma introducao curta de no maximo 2-3 frases. Nao escreva um post sobre a empresa em geral: escreva um post sobre ESTE documento.

Escreva uma analise completa em HTML puro para WordPress seguindo EXATAMENTE esta estrutura:

<!-- wp:html -->
<div style="background:linear-gradient(145deg,#171717,#262626);border-radius:14px;padding:20px;display:flex;gap:16px;align-items:center">
<div>{logo_html}</div>
<div style="color:#e5e5e5">
<h4 style="margin:0 0 8px 0"><mark style="background-color:rgba(0,0,0,0);color:#f6c453" class="has-inline-color">{descricao_doc}{data_titulo}</mark></h4>
<p style="font-size:14px;margin:0 0 4px 0;color:#e5e5e5">{publicado_em}<a href="{url_doc}" target="_blank" rel="noreferrer noopener" style="color:#f6c453">Documento oficial ({nome})</a></p>
<p style="font-size:14px;margin:0;color:#e5e5e5">Setor: {setor} - Empresa: {nome}</p>
</div>
</div>
<!-- /wp:html -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📄 O que o documento diz</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>1 frase explicando o que E esse tipo de documento e por que ele e publicado (ex.: o que e um resultado trimestral, um comunicado ao mercado, um fato relevante).</p><!-- /wp:paragraph -->
<!-- wp:list --><ul class="wp-block-list"><li>Ponto REAL do conteudo do documento.</li><li>Segundo ponto REAL do documento.</li><li>Terceiro ponto REAL do documento.</li></ul><!-- /wp:list -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💬 O que essa empresa faz?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Introducao curta de no maximo 2-3 frases, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📊 Indicadores Principais</h3><!-- /wp:heading -->
<!-- wp:table --><figure class="wp-block-table"><table><thead><tr><th>Indicador</th><th>Valor</th><th>Leitura</th></tr></thead><tbody><tr><td>Receita</td><td>R$ X bi</td><td>✅ ou ⚠️ + 2-4 palavras</td></tr><tr><td>Lucro</td><td>R$ X bi</td><td>✅ ou ⚠️ + 2-4 palavras</td></tr><tr><td>DY anual</td><td>X%</td><td>✅ ou ⚠️ + 2-4 palavras</td></tr></tbody></table></figure><!-- /wp:table -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">💰 DY Real?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>DY dentro do padrao historico ou inflado por extraordinarios?</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">⚠️ Pontos de Atenção</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Partindo do que o DOCUMENTO traz, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">👁️ Deve Ser Acompanhado</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Partindo do que o DOCUMENTO traz, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">✅ Boa Notícia</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Partindo do que o DOCUMENTO traz, com dados reais.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🔄 Mudou fundamento?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>Sim ou Nao com explicacao direta, partindo do documento.</p><!-- /wp:paragraph -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">📌 Merece Aporte?</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>💰 Foco em Renda:</strong> SELO<br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>📈 Foco em Valorização:</strong> SELO<br>Explicacao curta.</p><!-- /wp:paragraph -->
<!-- wp:quote --><blockquote class="wp-block-quote"><!-- wp:paragraph --><p>Conclusao em 2 frases.</p><!-- /wp:paragraph --></blockquote><!-- /wp:quote -->

<!-- wp:separator --><hr class="wp-block-separator has-alpha-channel-opacity"/><!-- /wp:separator -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🐟 O que isso significa pra você</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p>ESCREVA 2 a 3 frases no tom do Manjubinha (um peixinho iniciante que aprende junto), explicando de forma pratica o que esta analise significa para o pequeno investidor. Nao e recomendacao de compra ou venda.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">❓ Perguntas rápidas</h3><!-- /wp:heading -->
<!-- wp:paragraph --><p><strong>Pergunta real e comum sobre esta empresa?</strong><br>Resposta curta e direta.</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p><strong>Segunda pergunta real sobre esta empresa?</strong><br>Resposta curta e direta.</p><!-- /wp:paragraph -->

<!-- wp:heading {"level":3} --><h3 class="wp-block-heading">🔗 Leia também</h3><!-- /wp:heading -->
<!-- wp:list --><ul class="wp-block-list"><li><a href="https://manjubinhainvestidor.com.br/fiis-vs-acoes/">FIIs vs Ações: renda, riscos e como analisar</a></li><li><a href="https://manjubinhainvestidor.com.br/pontos-da-bolsa-indices/">O que são os pontos da bolsa e os índices</a></li></ul><!-- /wp:list -->

Regras:
- Linguagem simples e acolhedora para iniciantes. Use acentuacao e ortografia corretas do portugues (ç, ã, õ, é, í, ó, ê).
- Na secao "O que o documento diz": use os 3 bullets para o conteudo REAL do documento. Se o documento nao trouxer informacao relevante para o investidor, diga isso com transparencia em 1 bullet (ex.: "comunicado operacional, sem impacto para o acionista") e NUNCA invente conteudo.
- Na secao "Merece Aporte?", substitua a palavra SELO por EXATAMENTE um destes tres selos coloridos, conforme sua conclusao:
  COMPRAR -> <span style="background:#23c55e;color:#0a1118;padding:2px 12px;border-radius:12px;font-weight:700">COMPRAR</span>
  ACOMPANHAR -> <span style="background:#f6c453;color:#0a1118;padding:2px 12px;border-radius:12px;font-weight:700">ACOMPANHAR</span>
  EVITAR -> <span style="background:#525252;color:#fff;padding:2px 12px;border-radius:12px;font-weight:700">EVITAR</span>
- Na tabela de Indicadores, a coluna Leitura deve ser ✅ ou ⚠️ seguido de 2 a 4 palavras.
- Cada numero importante deve ganhar uma frase curta "isso importa porque..." conectando o dado ao bolso do investidor.
- NUNCA imprima "Data nao disponivel"; se faltar alguma data, simplesmente omita a mencao.
- TODO termo tecnico usado no post (DY, P/VP, EBITDA, TTM, alavancagem, tag along, guidance, payout, etc.) deve ser explicado entre parenteses na PRIMEIRA vez em que aparecer no texto. Explique apenas os termos que voce realmente usa; nao explique termos que nao aparecem.
- Mantenha os links da secao Leia tambem exatamente como estao no modelo.
- Maximo 950 palavras. Numeros reais, nunca invente dados. Sem markdown extra."""

def carregar(path, default):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default

def salvar(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def buscar_ultimo_doc(ticker, inv10_tipo):
    """
    Raspa o Investidor10 e retorna o documento mais recente do ativo.
    inv10_tipo: "fiis" ou "acoes"
    Retorna: {"id": str, "descricao": str, "data": str, "url_doc": str, "soup": BeautifulSoup} ou None
    O 'soup' e reaproveitado por garantir_logo para nao raspar a pagina duas vezes.
    """
    url = f"https://investidor10.com.br/{inv10_tipo}/{ticker.lower()}/"
    try:
        r = requests.get(url, timeout=15, headers=INV10_HEADERS)
        if r.status_code != 200:
            print(f"  Investidor10 {r.status_code} para {ticker}")
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.find("a", href=re.compile(r"link_comunicado"))
        if not link:
            print(f"  Nenhum comunicado encontrado para {ticker}")
            return None
        href = link["href"]
        doc_id = href.rstrip("/").split("/")[-1]
        # Extrai descricao e data via classes do Investidor10 (communication-card)
        # usa match exato para evitar bater em communication-card--disclosure
        card = link.find_parent("div", class_="communication-card")
        descricao, data = "Comunicado", ""
        if card:
            p = card.find("p", class_="communication-card--content")
            span = card.find("span", class_="card-date--content")
            if p:
                descricao = p.get_text(strip=True)[:100]
                # Para acoes a CVM usa "Categoria - Tipo": pega so o Tipo (parte apos " - ")
                if " - " in descricao:
                    descricao = descricao.split(" - ")[-1].strip()[:100]
            if span:
                data = span.get_text(strip=True)
        return {"id": doc_id, "descricao": descricao, "data": data, "url_doc": href, "soup": soup}
    except Exception as e:
        print(f"  Erro scraping {ticker}: {e}")
        return None

def _raspar_url_logo(soup):
    """
    Encontra a URL do logo real do ativo na pagina do Investidor10.
    O logo do cabecalho fica no container com id "sub-header-logo-md" (fallback
    "sub-header-logo"); a primeira <img> da pagina e do dropdown de navegacao e
    pode ser de outro ativo, entao NAO deve ser usada.
    Investidor10 serve o logo por-ativo em /storage/companies/<hash>.jpg (ou /storage/fiis/).
    FIIs sem logo caem num placeholder generico (building.svg) - nesses casos
    retornamos None e o post sai sem logo (nunca inventamos imagem).
    """
    if soup is None:
        return None
    header = soup.find(id="sub-header-logo-md") or soup.find(id="sub-header-logo")
    img = header.find("img") if header else None
    src = (img.get("src") or img.get("data-src") or "") if img else ""
    if re.search(r"/storage/(companies|fiis|stocks)/", src):
        if src.startswith("/"):
            src = "https://investidor10.com.br" + src
        return src
    return None

def _extensao_de(url, content_type=""):
    m = re.search(r"\.(jpg|jpeg|png|webp|gif|svg)(?:\?|$)", url.lower())
    if m:
        return m.group(1).replace("jpeg", "jpg")
    ct = (content_type or "").lower()
    if "png" in ct: return "png"
    if "webp" in ct: return "webp"
    if "svg" in ct: return "svg"
    if "gif" in ct: return "gif"
    return "jpg"

_MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif", "svg": "image/svg+xml"}

def garantir_logo(ativo, soup):
    """
    Garante que o ativo tenha um 'logo_wp' (URL do logo ja hospedado na Media Library do WP).
    Se ja tiver, retorna direto. Senao: raspa a URL no Investidor10, baixa a imagem e faz
    upload via /wp-json/wp/v2/media, salva o source_url em ativo['logo_wp'] e persiste config.json.
    NUNCA lanca excecao: qualquer falha retorna None (post sai sem logo).
    """
    try:
        if ativo.get("logo_wp"):
            return ativo["logo_wp"]
        ticker = ativo["ticker"]
        url_logo = _raspar_url_logo(soup)
        if not url_logo:
            print(f"  {ticker}: sem logo real no Investidor10 (segue sem logo)")
            return None
        img_resp = requests.get(url_logo, timeout=15, headers=INV10_HEADERS)
        if img_resp.status_code != 200 or not img_resp.content:
            print(f"  {ticker}: falha ao baixar logo ({img_resp.status_code})")
            return None
        ext = _extensao_de(url_logo, img_resp.headers.get("Content-Type", ""))
        mime = _MIME.get(ext, "image/jpeg")
        filename = f"logo-{ticker.lower()}.{ext}"
        up_headers = dict(WP_HEADERS)
        up_headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        up_headers["Content-Type"] = mime
        up = requests.post(f"{WP_API}/media", headers=up_headers, data=img_resp.content, timeout=30)
        if up.status_code not in (200, 201):
            print(f"  {ticker}: upload logo falhou {up.status_code}: {up.text[:200]}")
            return None
        source_url = up.json().get("source_url")
        if not source_url:
            print(f"  {ticker}: media sem source_url")
            return None
        ativo["logo_wp"] = source_url
        # persiste no config.json para nao re-raspar/re-upar na proxima rodada
        try:
            config = carregar(CONFIG, {})
            for grupo in ("fiis", "acoes"):
                for a in config.get(grupo, []):
                    if a.get("ticker") == ticker:
                        a["logo_wp"] = source_url
            salvar(CONFIG, config)
        except Exception as e:
            print(f"  {ticker}: nao persistiu logo_wp no config.json: {e}")
        print(f"  {ticker}: logo salvo em {source_url}")
        return source_url
    except Exception as e:
        print(f"  Logo falhou (segue sem logo): {e}")
        return None

def limpar_markdown(texto):
    """Remove blocos de codigo markdown que modelos mais novos adicionam mesmo sem pedir."""
    texto = texto.strip()
    fence = chr(96) * 3
    if texto.startswith(fence):
        linhas = texto.split("\n")
        linhas = linhas[1:]
        if linhas and linhas[-1].strip() == fence:
            linhas = linhas[:-1]
        texto = "\n".join(linhas).strip()
    return texto

def gemini(prompt):
    """
    Retorna:
      str   -> analise gerada com sucesso (ja sem markdown)
      None  -> falha por quota (429): nao gravar, retentar na proxima rodada
      False -> erro permanente: marcar sem_analise
    """
    time.sleep(5)
    payload = {"contents": [{"parts": [{"text": prompt}]}],
               "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
               "tools": [{"google_search": {}}]}
    so_quota = True
    for tentativa in range(3):
        r = requests.post(GEMINI_URL, json=payload, timeout=90)
        if r.status_code == 200:
            resp_json = r.json()
            candidates = resp_json.get("candidates", [])
            if not candidates: return False
            content_resp = candidates[0].get("content", {})
            parts = content_resp.get("parts", [])
            if not parts: return False
            # Pega o ultimo part do tipo text (pode haver parts de tool_use antes)
            textos = [p["text"] for p in parts if p.get("type","text") == "text" or "text" in p]
            texto = textos[-1] if textos else ""
            return limpar_markdown(texto)
        elif r.status_code == 429:
            print(f"  429 quota: aguardando 60s ({tentativa+1}/3)")
            time.sleep(60)
        elif r.status_code == 503:
            print(f"  503 sobrecarga: aguardando 30s ({tentativa+1}/3)")
            time.sleep(30)
        else:
            so_quota = False
            print(f"  Gemini {r.status_code}: {r.text[:200]}")
            return False
    if so_quota:
        print("  Gemini indisponivel apos 3 tentativas - retentara na proxima rodada")
        return None
    return False

# Categorias fixas do WordPress Manjubinha Hostinger
CAT_FII_PRINCIPAL = 13
CAT_ACAO_PRINCIPAL = 2

CAT_FII_TIPO = {
    "Papel": 30, "papel": 30,
    "Tijolo": 31, "tijolo": 31,
    "FoF": 26, "fof": 26,
    "Hibrido": 27, "hibrido": 27,
    "Fiagro": 25, "fiagro": 25,
}

CAT_FII_SEG = {
    "Logistico": 19,
    "Shoppings": 22,
    "Lajes Corp.": 18,
    "TVM": 23,
}

CAT_ACAO_SETOR = {
    "Bens Industriais": 3,
    "Consumo Ciclico": 4,
    "Consumo Nao Ciclico": 5,
    "Financeiro": 6,
    "Materiais Basicos": 7,
    "Petroleo, Gas e Biocombustiveis": 8,
    "Saude": 9,
    "Tecnologia da Informacao": 10,
    "Telecomunicacoes": 11,
    "Utilidade Publica": 12,
}

def get_fii_categories(ativo):
    cats = [CAT_FII_PRINCIPAL]
    tipo = ativo.get("tipo", "")
    seg  = ativo.get("segmento", "")
    if tipo.lower() == "tijolo" and seg:
        cat = CAT_FII_SEG.get(seg)
        cats.append(cat if cat else 31)
    elif tipo:
        cat = CAT_FII_TIPO.get(tipo)
        if cat:
            cats.append(cat)
    return cats

def get_acao_categories(ativo):
    cats = [CAT_ACAO_PRINCIPAL]
    setor = ativo.get("setor", "")
    cat = CAT_ACAO_SETOR.get(setor)
    if cat:
        cats.append(cat)
    return cats

def get_tag(ticker):
    r = requests.get(f"{WP_API}/tags", headers=WP_HEADERS, params={"search": ticker})
    tags = r.json()
    if isinstance(tags, list) and tags:
        return tags[0]["id"]
    nova = requests.post(f"{WP_API}/tags", headers=WP_HEADERS, json={"name": ticker})
    return nova.json().get("id")

def solicitar_indexacao(url):
    """Pede pro Google indexar a URL via Indexing API. Falha silenciosa - nunca trava o pipeline."""
    if not GOOGLE_INDEXING_KEY:
        return
    try:
        creds_info = json.loads(GOOGLE_INDEXING_KEY)
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/indexing"]
        )
        creds.refresh(GoogleAuthRequest())
        r = requests.post(
            "https://indexing.googleapis.com/v3/urlNotifications:publish",
            headers={"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"},
            json={"url": url, "type": "URL_UPDATED"},
            timeout=15
        )
        if r.status_code == 200:
            print(f"  Indexacao solicitada: {url}")
        else:
            print(f"  Indexing API erro {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  Indexing API falhou: {e}")

def publicar(titulo, conteudo, categorias, ticker):
    tag_id = get_tag(ticker)
    r = requests.post(f"{WP_API}/posts", headers=WP_HEADERS, json={
        "title": titulo, "content": conteudo,
        "status": "publish", "categories": categorias,
        "tags": [tag_id] if tag_id else []
    })
    if r.status_code in (200, 201):
        url = r.json()["link"]
        print(f"  OK {url}")
        solicitar_indexacao(url)
        return url
    print(f"  WP ERRO {r.status_code}: {r.text[:300]}")
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

def proximos(lista, controle, n):
    """Retorna os N ativos com a data de ultima analise mais antiga (carrossel continuo)."""
    pendentes = []
    for ativo in lista:
        t = ativo["ticker"]
        ultima = controle.get(t, {}).get("ultima", "0")
        pendentes.append((ultima, ativo))
    pendentes.sort(key=lambda x: x[0])
    return [a for _, a in pendentes[:n]]

def processar_ativo(ativo, controle, tipo):
    t    = ativo["ticker"]
    hoje = datetime.today().strftime("%Y-%m-%d")
    print(f"  -> {t} ({ativo['nome']})")

    # 1. Busca ultimo doc no Investidor10
    inv10_tipo = "fiis" if tipo == "fii" else "acoes"
    doc = buscar_ultimo_doc(t, inv10_tipo)
    if not doc:
        print(f"  {t} sem doc disponivel - tentara na proxima rodada")
        return  # nao atualiza ultima: ativo fica no inicio da fila para retentar logo

    # 2. Verifica se esse doc ja foi publicado
    chave = f"{t}_{doc['id']}"
    if controle.get(chave, {}).get("status") == "ok":
        print(f"  {t} doc ja publicado ({doc['descricao']} | {doc['data']}) - sem novidade")
        controle.setdefault(t, {})["ultima"] = hoje  # empurra para o fim da fila
        salvar(CONTROLE, controle)
        return

    # 2b. Garante logo do ativo (reaproveita o soup ja raspado; falha nunca derruba a analise)
    logo_url = garantir_logo(ativo, doc.get("soup"))
    if logo_url:
        logo_html = (f'<img src="{logo_url}" alt="Logo {t}" '
                     'style="width:48px;height:48px;border-radius:10px;object-fit:contain;'
                     'background:#fff;padding:4px"/>')
    else:
        logo_html = ""

    # 2c. Tratamento de data vazia: se nao houver data, os fragmentos que a exibiriam somem
    data_doc   = doc["data"] or ""
    data_sufixo = f" de {data_doc}" if data_doc else ""      # "... documento: X de 01/01"
    data_titulo = f" - {data_doc}" if data_doc else ""        # "<mark>X - 01/01</mark>"
    publicado_em = f"Publicado em: {data_doc} - " if data_doc else ""  # box: "Publicado em: ... - "

    # 3. Monta prompt com info do documento
    print(f"  Novo doc: {doc['descricao']} ({data_doc or 'sem data'})")
    if tipo == "fii":
        prompt = PROMPT_FII \
            .replace("{ticker}", t) \
            .replace("{nome}", ativo["nome"]) \
            .replace("{descricao_doc}", doc["descricao"]) \
            .replace("{data_doc}", data_doc) \
            .replace("{data_sufixo}", data_sufixo) \
            .replace("{data_titulo}", data_titulo) \
            .replace("{publicado_em}", publicado_em) \
            .replace("{url_doc}", doc["url_doc"]) \
            .replace("{logo_html}", logo_html) \
            .replace("{ri_url}", ativo.get("ri_url", "")) \
            .replace("{tipo}", ativo.get("tipo", "")) \
            .replace("{gestora}", ativo.get("gestora", ""))
        categorias = get_fii_categories(ativo)
    else:
        prompt = PROMPT_ACAO \
            .replace("{ticker}", t) \
            .replace("{nome}", ativo["nome"]) \
            .replace("{descricao_doc}", doc["descricao"]) \
            .replace("{data_doc}", data_doc) \
            .replace("{data_sufixo}", data_sufixo) \
            .replace("{data_titulo}", data_titulo) \
            .replace("{publicado_em}", publicado_em) \
            .replace("{url_doc}", doc["url_doc"]) \
            .replace("{logo_html}", logo_html) \
            .replace("{ri_url}", ativo.get("ri_url", "")) \
            .replace("{setor}", ativo.get("setor", ""))
        categorias = get_acao_categories(ativo)

    print(f"  Categorias: {categorias}")
    print("  Gemini...")
    analise = gemini(prompt)

    if analise is None:
        print(f"  {t} adiado - quota Gemini, retenta na proxima rodada")
        return  # nao atualiza ultima nem chave

    if analise is False:
        print(f"  {t} erro permanente Gemini - marcando doc como sem_analise")
        controle[chave] = {"status": "sem_analise", "data": hoje}
        controle.setdefault(t, {})["ultima"] = hoje
        salvar(CONTROLE, controle)
        return

    mes    = datetime.today().strftime("%m/%Y")
    titulo = f"{t} - {ativo['nome']} | {doc['descricao']} {mes}"
    print("  Publicando...")
    url = publicar(titulo, analise, categorias, t)
    if url:
        atualizar_ranking(t, url, tipo)
        controle[chave] = {"status": "ok", "url": url, "data": hoje, "descricao": doc["descricao"]}
        controle.setdefault(t, {})["ultima"] = hoje
        salvar(CONTROLE, controle)
        print(f"  Salvo: {chave}")
    else:
        print(f"  {t} erro WP - retenta na proxima rodada")
        # nao atualiza: retenta logo

def main():
    print(f"Manjubinha - {datetime.today().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Rodada: 2 FIIs + 2 Acoes")
    config   = carregar(CONFIG, {})
    controle = carregar(CONTROLE, {})
    fiis_rodada  = proximos(config.get("fiis",  []), controle, POR_RODADA)
    acoes_rodada = proximos(config.get("acoes", []), controle, POR_RODADA)
    if not fiis_rodada and not acoes_rodada:
        print("Nenhum ativo configurado.")
        return
    print(f"FIIs:  {[a['ticker'] for a in fiis_rodada]}")
    for ativo in fiis_rodada:
        processar_ativo(ativo, controle, "fii")
    print(f"Acoes: {[a['ticker'] for a in acoes_rodada]}")
    for ativo in acoes_rodada:
        processar_ativo(ativo, controle, "acao")
    # Resumo
    total_fiis  = len(config.get("fiis",  []))
    total_acoes = len(config.get("acoes", []))
    hoje = datetime.today().strftime("%Y-%m-%d")
    atualizados_f = sum(1 for a in config.get("fiis",  []) if controle.get(a["ticker"], {}).get("ultima") == hoje)
    atualizados_a = sum(1 for a in config.get("acoes", []) if controle.get(a["ticker"], {}).get("ultima") == hoje)
    print(f"Concluido! Verificados hoje: {atualizados_f}/{total_fiis} FIIs, {atualizados_a}/{total_acoes} Acoes.")

if __name__ == "__main__":
    main()
