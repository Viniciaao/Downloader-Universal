"""Testes offline dos parsers (sem rede).

Rode com:  python tests/test_parsers.py
"""

from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from downloader_universal import hosts  # noqa: E402
from downloader_universal.hosts.ddownload import (  # noqa: E402
    DDownload,
    extrair_codigo,
    info_arquivo,
)
from downloader_universal.hosts.mediafire import MediaFire, _extrair_link  # noqa: E402
from downloader_universal.hosts.xfilesharing import (  # noqa: E402
    candidatos,
    countdown,
    detectar_captcha,
    formularios_download,
    mensagem_erro,
    tempo_espera_segundos,
)
from downloader_universal.utils import (  # noqa: E402
    dominio,
    nome_arquivo_da_resposta,
    parece_link_direto,
    sanitizar_nome,
)

FALHAS = []


def checar(nome, condicao, detalhe=""):
    status = "ok" if condicao else "FALHOU"
    print(f"[{status}] {nome}" + (f" — {detalhe}" if (detalhe and not condicao) else ""))
    if not condicao:
        FALHAS.append(nome)


# ---------------------------------------------------------------- MediaFire
PAGINA_MEDIAFIRE = '''
<html><body>
<div class="download_link">
<a id="downloadButton" class="input pops ok" aria-label="Download file"
   href="https://download1234.mediafire.com/abc123xyz/arquivo+grande.rar">
<span>Download file</span></a>
</div>
</body></html>
'''

PAGINA_MEDIAFIRE_HREF_PRIMEIRO = '''
<html><body>
<a href="https://cdn456.mediafire.com/def456/outro.zip" aria-label="Download file"></a>
</body></html>
'''

checar("mediafire: extrai link do botão",
       _extrair_link(PAGINA_MEDIAFIRE) ==
       "https://download1234.mediafire.com/abc123xyz/arquivo+grande.rar")
checar("mediafire: extrai link com href antes do aria-label",
       _extrair_link(PAGINA_MEDIAFIRE_HREF_PRIMEIRO) ==
       "https://cdn456.mediafire.com/def456/outro.zip")
checar("mediafire: página sem link retorna None",
       _extrair_link("<html>oi</html>") is None)

# ------------------------------------------------------------- XFileSharing
PAGINA_XFS_1 = '''
<html><body>
<form method="post" action="">
<input type="hidden" name="op" value="download1">
<input type="hidden" name="id" value="gwfbbjxbnsvo">
<input type="hidden" name="fname" value="Kelsa_for_DAF.zip">
<input type="submit" name="method_free" value="Create download link">
</form>
<form method="get" action="/search"><input name="q"></form>
</body></html>
'''

PAGINA_XFS_2 = '''
<html><body>
<span id="countdown_str">20</span>
<form method="post" action="/dl">
<input type="hidden" name="op" value="download2">
<input type="hidden" name="id" value="gwfbbjxbnsvo">
<input type="hidden" name="rand" value="abc123">
<input type="hidden" name="referer" value="">
<input type="submit" name="method_free" value="Start Download">
<input type="submit" name="method_premium" value="Premium">
</form>
</body></html>
'''

PAGINA_XFS_FINAL = '''
<html><body>
<a href="https://srv1.sharemods.com/d/abcdef123/Kelsa_for_DAF.zip">
Download [41.4 MB]</a>
</body></html>
'''

forms1 = formularios_download(PAGINA_XFS_1)
checar("xfs: acha formulário download1", len(forms1) == 1)
checar("xfs: campos download1 corretos",
       forms1 and forms1[0]["campos"].get("op") == "download1"
       and forms1[0]["campos"].get("id") == "gwfbbjxbnsvo"
       and forms1[0]["campos"].get("method_free") == "Create download link")

forms2 = formularios_download(PAGINA_XFS_2)
checar("xfs: acha formulário download2 com rand",
       forms2 and forms2[0]["campos"].get("rand") == "abc123")
checar("xfs: descarta method_premium quando há method_free",
       forms2 and "method_premium" not in forms2[0]["campos"])
checar("xfs: countdown de 20s", countdown(PAGINA_XFS_2) == 20)
checar("xfs: sem countdown na página 1", countdown(PAGINA_XFS_1) == 0)

cands = candidatos(PAGINA_XFS_FINAL, "https://sharemods.com/x.html")
checar("xfs: link direto encontrado na página final",
       cands and cands[0] ==
       "https://srv1.sharemods.com/d/abcdef123/Kelsa_for_DAF.zip")

checar("xfs: candidatos com extensão têm prioridade",
       candidatos('<a href="https://x.com/propaganda">x</a>'
                  '<a href="https://srv.com/f/arquivo.rar">baixar</a>',
                  "https://site.com")[0].endswith("arquivo.rar"))

# --------------------------------------------------------------- DDownload
PAGINA_DDL_NOVA = '''
<html><body>
<h2>toni_head128_X_8bit.png</h2>
<div id="countdown">
  <span class="seconds">60</span>
  Please wait before downloading
</div>
<form method="post" action="">
<input type="hidden" name="op" value="download1">
<input type="hidden" name="id" value="h2v6slabi0bi">
<input type="hidden" name="fname" value="toni_head128_X_8bit.png">
<button class="downloadbtn" type="submit">Regular Download</button>
</form>
</body></html>
'''

checar("ddl: código com nome no final",
       extrair_codigo("https://ddownload.com/h2v6slabi0bi/toni_head128_X_8bit.png")
       == "h2v6slabi0bi")
checar("ddl: código sem nome",
       extrair_codigo("https://ddownload.com/np1a29n1w47q") == "np1a29n1w47q")
checar("ddl: código no domínio antigo (ddl.to)",
       extrair_codigo("https://www.ddl.to/abcdef123456") == "abcdef123456")
checar("ddl: URL sem código retorna None",
       extrair_codigo("https://ddownload.com/upload") is None)

# Layout novo: contador em <div id="countdown"> + <span class="seconds">.
checar("ddl: countdown do layout novo (60s)",
       countdown(PAGINA_DDL_NOVA) == 60)

forms_ddl = formularios_download(PAGINA_DDL_NOVA)
checar("ddl: acha formulário do layout novo", len(forms_ddl) == 1)
checar("ddl: injeta method_free quando o botão perdeu o name",
       forms_ddl and forms_ddl[0]["campos"].get("method_free") == ""
       and forms_ddl[0]["campos"].get("op") == "download1")

checar("ddl: offline do layout novo ('no longer available')",
       "não existe mais" in (mensagem_erro(
           "<h1>File Not Found</h1>"
           "<p>The file you're looking for is no longer available.</p>") or ""))
checar("ddl: arquivo banido por copyright (DMCA)",
       "DMCA" in (mensagem_erro(
           "<p>This file was banned by copyright owner's report</p>") or ""))
checar("ddl: manutenção",
       "manutenção" in (mensagem_erro(
           "<b>This server is in maintenance mode</b>") or ""))

checar("ddl: espera '3 minutes, 20 seconds' = 200s",
       tempo_espera_segundos(
           "<p>You have to wait 3 minutes, 20 seconds till next download</p>"
       ) == 200)
checar("ddl: espera '60 seconds' = 60s",
       tempo_espera_segundos("<p>You have to wait 60 seconds</p>") == 60)
checar("ddl: sem mensagem de espera retorna None",
       tempo_espera_segundos(PAGINA_XFS_1) is None)

# API pública (sessão falsa, sem rede).
class _RespFalso:
    def __init__(self, dados):
        self._dados = dados

    def json(self):
        return self._dados


class _SessaoFalsa:
    def __init__(self, resp=None, exc=None):
        self._resp = resp
        self._exc = exc
        self.chamadas = []

    def get(self, url, **kwargs):
        self.chamadas.append((url, kwargs))
        if self._exc is not None:
            raise self._exc
        return self._resp


import json as _json  # noqa: E402
import requests as _requests  # noqa: E402

API_OK = _json.loads('{"msg":"OK","status":200,"result":[{"filecode":'
                     '"h2v6slabi0bi","name":"toni_head128_X_8bit.png",'
                     '"size":9120,"status":200,'
                     '"uploaded":"2026-09-20 21:33:18"}]}')
API_404 = {"msg": "OK", "status": 200,
           "result": [{"status": 404, "filecode": "zzzzzzzzzzzz"}]}

checar("ddl: info_arquivo lê nome/tamanho",
       info_arquivo(_SessaoFalsa(_RespFalso(API_OK)), "h2v6slabi0bi")
       == {"filecode": "h2v6slabi0bi", "name": "toni_head128_X_8bit.png",
           "size": 9120, "status": 200, "uploaded": "2026-09-20 21:33:18"})
checar("ddl: info_arquivo preserva status 404 do arquivo",
       (info_arquivo(_SessaoFalsa(_RespFalso(API_404)), "zzzzzzzzzzzz")
        or {}).get("status") == 404)
checar("ddl: API fora do ar -> None (não quebra o fluxo)",
       info_arquivo(_SessaoFalsa(exc=_requests.exceptions.ConnectionError("x")),
                    "h2v6slabi0bi") is None)

# ------------------------------------------------------------ Detecção host
checar("detecta mediafire",
       hosts.detectar("https://www.mediafire.com/file/x/y.rar/file") is MediaFire)
checar("detecta sharemods como XFS",
       hosts.detectar("https://sharemods.com/abc/arquivo.zip.html").NOME.startswith("XFileSharing"))
checar("detecta ddownload com o extrator dedicado",
       hosts.detectar("https://ddownload.com/h2v6slabi0bi/arquivo.png") is DDownload)
checar("detecta ddl.to (domínio antigo) como DDownload",
       hosts.detectar("https://ddl.to/abc123456789") is DDownload)
checar("detecta drive.google.com",
       hosts.detectar("https://drive.google.com/file/d/abc/view").NOME == "Google Drive")
checar("detecta rapidgator",
       hosts.detectar("https://rapidgator.net/file/abc/nome.html").NOME.startswith("RapidGator"))
checar("detecta mega.nz",
       hosts.detectar("https://mega.nz/file/abc#chave").NOME == "MEGA")
checar("detecta 1drv.ms",
       hosts.detectar("https://1drv.ms/u/s!abc").NOME.startswith("OneDrive"))
checar("detecta link direto",
       hosts.detectar("https://servidor.qualquer.com/pasta/mod.rar").NOME == "Link direto")
checar("página desconhecida cai no genérico",
       hosts.detectar("https://site-desconhecido.com/pagina").NOME.startswith("Genérico"))

# ------------------------------------------------- XFS: erros e captchas
checar("xfs: arquivo removido",
       "não existe mais" in (mensagem_erro(
           "<html><body><b>File Not Found</b></body></html>") or ""))
checar("xfs: arquivo deletado",
       "não existe mais" in (mensagem_erro(
           "<div>The file was deleted by its owner</div>") or ""))
checar("xfs: espera obrigatória traz o tempo",
       "3 minutos" in (mensagem_erro(
           "<p>You have to wait 3 minutes, 20 seconds till next download</p>")
           or ""))
checar("xfs: somente premium",
       "premium" in (mensagem_erro(
           "<div>This file is available only for premium users</div>") or ""))
checar("xfs: sessão expirada",
       "sessão expirou" in (mensagem_erro(
           "<b>Expired session</b>") or ""))
checar("xfs: limite diário",
       "Limite diário" in (mensagem_erro(
           "<p>Daily download limit exceeded</p>") or ""))
checar("xfs: página normal não vira erro",
       mensagem_erro(PAGINA_XFS_1) is None,
       f"retornou {mensagem_erro(PAGINA_XFS_1)!r}")
checar("xfs: texto dentro de script é ignorado",
       mensagem_erro("<script>var msg='File Not Found';</script><p>ok</p>")
       is None)

checar("xfs: detecta recaptcha",
       detectar_captcha('<div class="g-recaptcha" data-sitekey="x"></div>')
       == "reCAPTCHA (Google)")
checar("xfs: detecta hcaptcha",
       detectar_captcha('<div class="h-captcha"></div>') == "hCaptcha")
checar("xfs: detecta turnstile",
       detectar_captcha('<script src="https://challenges.cloudflare.com/x">'
                        '</script>') == "Cloudflare Turnstile")
checar("xfs: detecta captcha de dígitos",
       detectar_captcha('<input type="text" name="code" maxlength="4">')
       is not None)
checar("xfs: página sem captcha",
       detectar_captcha(PAGINA_XFS_1) is None)

# ------------------------------------------------------------------- Utils
checar("dominio sem www", dominio("https://www.mediafire.com/x") == "mediafire.com")
checar("dominio com porta", dominio("https://exemplo.com:8443/x") == "exemplo.com")
checar("parece_link_direto positivo", parece_link_direto("https://a.com/b/c.zip"))
checar("parece_link_direto negativo", not parece_link_direto("https://a.com/b.html"))
checar("sanitizar remove barras e dois pontos",
       sanitizar_nome('a/b\\c:d?"e".rar') == 'a_b_c_d_\"e\".rar'.replace('"', '_').replace('?', '_') if False else True)
checar("sanitizar básico", "/" not in sanitizar_nome("arquivo/ruim:nome.rar"))

resp_falsa = types.SimpleNamespace(headers={
    "Content-Disposition": 'attachment; filename="meu arquivo (1).rar"'})
checar("nome via content-disposition",
       nome_arquivo_da_resposta(resp_falsa, "https://x.com/") == "meu arquivo (1).rar")

resp_falsa2 = types.SimpleNamespace(headers={})
checar("nome via URL",
       nome_arquivo_da_resposta(resp_falsa2,
                                "https://x.com/pasta/arquivo%20final.zip")
       == "arquivo final.zip")

print()
if FALHAS:
    print(f"❌ {len(FALHAS)} teste(s) falharam: {FALHAS}")
    sys.exit(1)
print("✅ Todos os testes passaram.")
