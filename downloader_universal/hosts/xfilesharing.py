"""Motor para sites baseados em XFileSharing (XFS).

XFS é o script usado por centenas de sites de hospedagem de arquivos
(Sharemods, DDownload, UsersDrive, UploadRar, FileFox, HexUpload, ...).

Fluxo típico:
  1. GET na página do arquivo
  2. POST dos formulários escondidos (op=download1 -> op=download2 ...)
  3. Em algum momento aparece o link direto (às vezes depois de uma espera)

Este módulo automatiza as etapas 1-3 de forma genérica: procura formulários
com ``op=download*``, envia-os em sequência, respeita contagens regressivas e
caça o link direto na resposta.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..config import CONFIG
from ..transfer import DownloadError, RespostaHTML, stream_download
from ..utils import log, parece_link_direto, sessao

#: Sites conhecidos que usam XFS (outros são detectados automaticamente
#: pelo extrator genérico quando a página contém formulários op=download).
DOMINIOS_XFS = {
    "sharemods.com",
    "ddownload.com",
    "usersdrive.com",
    "uploadrar.com",
    "filefox.com",
    "hexupload.net",
}

# Ordem importa: padrões mais específicos primeiro.
PADROES_LINK = [
    re.compile(r'id=["\']direct_link["\'][^>]*value=["\']([^"\']+)["\']', re.I),
    re.compile(r'name=["\']direct_link["\'][^>]*value=["\']([^"\']+)["\']', re.I),
    re.compile(r'<textarea[^>]*id=["\']direct_link["\'][^>]*>\s*([^<\s][^<]*)', re.I),
    # Âncoras com texto típico de download.
    re.compile(
        r'href=["\']([^"\']+)["\'][^>]*>\s*(?:<[^>]{0,120}>\s*)*'
        r'(?:Direct\s+Download(?:\s+Link)?|Start\s+Download|Free\s+Download|'
        r'Slow\s+Download|Normal\s+Download|Baixar|Clique\s+aqui\s+para\s+baixar)',
        re.I,
    ),
    re.compile(
        r'href=["\']([^"\']+)["\'][^>]*>\s*(?:<[^>]{0,120}>\s*)*Download\s*\[',
        re.I,
    ),
    re.compile(
        r'id=["\'][^"\']*download[^"\']*["\'][^>]*href=["\']([^"\']+)["\']', re.I),
    re.compile(
        r'href=["\']([^"\']+)["\'][^>]*id=["\'][^"\']*download[^"\']*["\']', re.I),
    # Redirecionamentos por JavaScript / meta refresh.
    re.compile(r'window\.location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', re.I),
    re.compile(
        r'<meta[^>]+http-equiv=["\']refresh["\'][^>]*url=([^"\';\s>]+)', re.I),
]

PADROES_COUNTDOWN = [
    re.compile(r'id=["\']countdown_str["\'][^>]*>\s*(\d+)', re.I),
    re.compile(r'id=["\']countdown["\'][^>]*(?:value=["\']|>)\s*(\d+)', re.I),
    re.compile(r'var\s+wait\s*=\s*(\d+)', re.I),
]

RE_FORM_XFS = re.compile(r'name=["\']?op["\']?\s+value=["\']download', re.I)

#: Mensagens de erro típicas do XFS -> explicação amigável.
#: Ordem importa: a primeira que casar é usada.
PADROES_ERRO = [
    (re.compile(r"file\s+not\s+found|no\s+such\s+file|file\s+was\s+deleted|"
                r"file\s+(?:has\s+been\s+)?removed|arquivo\s+n[ãa]o\s+encontrado",
                re.I),
     "O arquivo não existe mais (foi removido ou o link expirou)."),
    (re.compile(r"you\s+have\s+to\s+wait\s+(?:(\d+)\s*(minute|hour|second)s?"
                r"(?:[^.]*?(\d+)\s*(minute|hour|second)s?)?)", re.I),
     "O site exige espera entre downloads gratuitos{detalhe}. "
     "Aguarde e tente de novo, ou troque de IP."),
    (re.compile(r"you\s+can\s+download\s+files\s+up\s+to|"
                r"available\s+only\s+for\s+premium|premium\s+(?:users|members)\s+only|"
                r"become\s+premium|this\s+file\s+is\s+available\s+only", re.I),
     "Este arquivo só pode ser baixado com conta premium do site."),
    (re.compile(r"expired\s+session|security\s+error|session\s+expired|"
                r"invalid\s+(?:file\s+)?(?:link|url)", re.I),
     "A sessão expirou ou o site recusou a requisição (proteção anti-bot). "
     "Tente novamente daqui a alguns minutos."),
    (re.compile(r"skipped\s+countdown|wrong\s+captcha|captcha\s+error", re.I),
     "O site recusou a etapa de verificação (captcha/contagem regressiva)."),
    (re.compile(r"daily\s+download\s+limit|download\s+limit\s+exceeded|"
                r"limite\s+di[áa]rio", re.I),
     "Limite diário de downloads gratuitos atingido para este IP."),
    (re.compile(r"ip\s+address.{0,40}(?:already|another)\s+download|"
                r"another\s+download.{0,40}in\s+progress", re.I),
     "Já existe outro download em andamento a partir deste IP. "
     "Termine/cancele o outro e tente de novo."),
]

PADROES_CAPTCHA = [
    (re.compile(r"g-recaptcha|recaptcha/api", re.I), "reCAPTCHA (Google)"),
    (re.compile(r"h-captcha|hcaptcha\.com", re.I), "hCaptcha"),
    (re.compile(r"turnstile|challenges\.cloudflare\.com", re.I),
     "Cloudflare Turnstile"),
    (re.compile(r'<input[^>]+name=["\']code["\']', re.I),
     "captcha de dígitos do XFS"),
    (re.compile(r"padding-left:\s*\d+px;\s*padding-top:\s*\d+px", re.I),
     "captcha de dígitos posicionados por CSS"),
]


def mensagem_erro(html):
    """Explicação amigável se o HTML contiver um erro conhecido do XFS."""
    texto = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "",
                   flags=re.I | re.S)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    for padrao, explicacao in PADROES_ERRO:
        m = padrao.search(texto)
        if not m:
            continue
        grupos = list(m.groups())
        unidades = {"second": "segundos", "minute": "minutos",
                    "hour": "horas"}
        partes = [f"{grupos[i]} "
                  f"{unidades.get(grupos[i + 1].lower(), grupos[i + 1])}"
                  for i in range(0, len(grupos) - 1, 2)
                  if grupos[i] and grupos[i + 1]]
        detalhe = " (" + " e ".join(partes) + ")" if partes else ""
        return explicacao.format(detalhe=detalhe)
    return None


def detectar_captcha(html):
    """Nome do captcha presente na página, ou None."""
    for padrao, nome in PADROES_CAPTCHA:
        if padrao.search(html or ""):
            return nome
    return None


def _assinatura(html):
    """Assinatura do conteúdo útil da página (para detectar repetição)."""
    corpo = re.sub(r"\s+", " ", html or "")
    # remove tokens que mudam a cada requisição (rand, csrf, etc.)
    corpo = re.sub(r'value=["\'][0-9a-f]{8,}["\']', "", corpo, flags=re.I)
    return hashlib.sha1(corpo.encode("utf-8", "replace")).hexdigest()


def _salvar_diagnostico(html, url):
    """Salva o último HTML para inspeção; devolve o caminho (ou None)."""
    try:
        destino = os.path.join(tempfile.gettempdir(),
                               f"xfs_debug_{abs(hash(url)) % 10**8}.html")
        with open(destino, "w", encoding="utf-8", errors="replace") as fh:
            fh.write(html or "")
        return destino
    except OSError:
        return None


def candidatos(html, base_url):
    """Lista de possíveis links diretos encontrados no HTML (com prioridade)."""
    achados = []
    for padrao in PADROES_LINK:
        for m in padrao.finditer(html):
            link = (m.group(1) or "").strip()
            if not link or link.startswith("#"):
                continue
            if link.lower().startswith(("javascript:", "mailto:")):
                continue
            link = urljoin(base_url, link)
            if link not in achados:
                achados.append(link)
    # Links com extensão de arquivo têm prioridade máxima.
    com_ext = [l for l in achados if parece_link_direto(l)]
    return com_ext + [l for l in achados if l not in com_ext]


def countdown(html):
    """Segundos de espera exigidos pelo site (0 se não houver)."""
    for padrao in PADROES_COUNTDOWN:
        m = padrao.search(html)
        if m:
            return min(int(m.group(1)), 120)
    return 0


def formularios_download(html):
    """Formulários da página com ``op=download*`` (etapas do XFS)."""
    sopa = BeautifulSoup(html, "html.parser")
    formularios = []
    for form in sopa.find_all("form"):
        campos = {}
        for inp in form.find_all(["input", "button"]):
            nome = inp.get("name")
            if not nome:
                continue
            tipo = (inp.get("type") or "text").lower()
            valor = inp.get("value") or ""
            if (tipo in ("hidden", "submit", "button")
                    or nome.lower() in {"op", "id", "rand", "referer", "fname",
                                        "method_free", "method_premium"}):
                campos[nome] = valor
        if str(campos.get("op", "")).lower().startswith("download"):
            if "method_free" in campos:
                campos.pop("method_premium", None)
            formularios.append({"action": form.get("action") or "",
                                "campos": campos})
    return formularios


def baixar_xfs(url, pasta, *, sess=None, html_inicial=None, force=False):
    """Baixa um arquivo percorrendo as etapas XFS até achar o link direto."""
    sess = sess or sessao()
    sess.headers["Referer"] = url

    html = html_inicial
    url_atual = url
    motivo = None          # explicação específica encontrada na página
    assinaturas = []       # para detectar páginas repetidas (loop)

    for etapa in range(1, 8):
        if html is None:
            resp = sess.get(url_atual, timeout=CONFIG["timeout"],
                            allow_redirects=True)
            resp.raise_for_status()
            html = resp.text
            url_atual = str(resp.url)

        # 0) A página informa algum erro conhecido do XFS?
        erro = mensagem_erro(html)
        if erro:
            motivo = erro
            break

        # 1) Já existe link direto na página?
        for link in candidatos(html, url_atual):
            try:
                return stream_download(link, pasta, sess=sess,
                                       referer=url_atual, force=force)
            except RespostaHTML:
                continue  # não era o arquivo; tenta o próximo candidato

        # 2) Existe formulário de próxima etapa?
        formularios = formularios_download(html)
        if not formularios:
            captcha = detectar_captcha(html)
            if captcha:
                motivo = (f"A página exige verificação por {captcha}, "
                          "que não pode ser resolvida automaticamente.")
            break
        formulario = formularios[0]

        # 3) A página é a mesma da etapa anterior? Então estamos em loop.
        assinatura = _assinatura(html)
        if assinatura in assinaturas:
            captcha = detectar_captcha(html)
            if captcha:
                motivo = (f"O site repetiu a mesma página: ela exige "
                          f"{captcha}, que não pode ser resolvido "
                          "automaticamente.")
            else:
                motivo = ("O site devolveu a mesma página de formulário duas "
                          "vezes seguidas (etapa " f"{etapa}"
                          "). Normalmente isso significa verificação "
                          "anti-bot, espera obrigatória ou sessão recusada.")
            break
        assinaturas.append(assinatura)

        espera = countdown(html)
        if espera:
            log(f"⏳ Aguardando {espera}s (exigência do site)...")
            time.sleep(espera)

        alvo = urljoin(url_atual, formulario["action"]) or url_atual
        log(f"   ↳ etapa {etapa}: enviando formulário "
            f"(op={formulario['campos'].get('op', '?')})")
        resp = sess.post(alvo, data=formulario["campos"],
                         timeout=CONFIG["timeout"], allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        url_atual = str(resp.url)

    if motivo is None:
        motivo = ("Percorri todas as etapas e nenhuma página trouxe o link "
                  "direto. O site pode ter mudado o formato da página.")

    partes = [f"Não consegui baixar {url}.", motivo]
    caminho = _salvar_diagnostico(html, url)
    if caminho and CONFIG.get("verbose", True):
        partes.append(f"HTML da última página salvo em: {caminho}")
    raise DownloadError(" ".join(partes))


class XFileSharing:
    NOME = "XFileSharing (Sharemods, DDownload e similares)"
    DOMINIOS = DOMINIOS_XFS

    @staticmethod
    def baixar(url, pasta, force=False):
        return baixar_xfs(url, pasta, force=force)
