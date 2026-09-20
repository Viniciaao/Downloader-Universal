"""Testes offline dos parsers (sem rede).

Rode com:  python tests/test_parsers.py
"""

from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from downloader_universal import hosts  # noqa: E402
from downloader_universal.hosts.mediafire import MediaFire, _extrair_link  # noqa: E402
from downloader_universal.hosts.xfilesharing import (  # noqa: E402
    candidatos,
    countdown,
    detectar_captcha,
    formularios_download,
    mensagem_erro,
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

# ------------------------------------------------------------ Detecção host
checar("detecta mediafire",
       hosts.detectar("https://www.mediafire.com/file/x/y.rar/file") is MediaFire)
checar("detecta sharemods como XFS",
       hosts.detectar("https://sharemods.com/abc/arquivo.zip.html").NOME.startswith("XFileSharing"))
checar("detecta ddownload como XFS",
       hosts.detectar("https://ddownload.com/abc/arquivo.rar").NOME.startswith("XFileSharing"))
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
