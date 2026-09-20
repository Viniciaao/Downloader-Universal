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

import requests
from bs4 import BeautifulSoup

from ..config import CONFIG
from ..transfer import DownloadError, RespostaHTML, stream_download
from ..utils import log, parece_link_direto, sessao

#: Sites conhecidos que usam XFS (outros são detectados automaticamente
#: pelo extrator genérico quando a página contém formulários op=download).
#: DDownload tem extrator próprio (hosts/ddownload.py) e foi removido daqui.
DOMINIOS_XFS = {
    "sharemods.com",
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
                r"file\s+(?:has\s+been\s+)?removed|no\s+longer\s+available|"
                r"cannot\s+be\s+accessed|"
                r"arquivo\s+n[ãa]o\s+encontrado",
                re.I),
     "O arquivo não existe mais (foi removido ou o link expirou)."),
    (re.compile(r"banned\s+by\s+copyright|copyright\s+owner['’]s?\s+report|"
                r"removed\s+(?:due\s+to|for)\s+(?:dmca|copyright)|\bdmca\b",
                re.I),
     "O arquivo foi removido por direitos autorais (DMCA)."),
    (re.compile(r"you\s+have\s+to\s+wait\s+(?:(\d+)\s*(minute|hour|second)s?"
                r"(?:[^.]*?(\d+)\s*(minute|hour|second)s?)?)", re.I),
     "O site exige espera entre downloads gratuitos{detalhe}. "
     "Aguarde e tente de novo, ou troque de IP."),
    (re.compile(r"maintenance\s+mode|server\s+is\s+in\s+maintenance", re.I),
     "O servidor está em manutenção. Tente novamente em alguns minutos."),
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


def texto_puro(html):
    """Texto visível do HTML (sem script/style), espremido em uma linha."""
    texto = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "",
                   flags=re.I | re.S)
    texto = re.sub(r"<[^>]+>", " ", texto)
    return re.sub(r"\s+", " ", texto)


def mensagem_erro(html):
    """Explicação amigável se o HTML contiver um erro conhecido do XFS."""
    texto = texto_puro(html)
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


def tempo_espera_segundos(html):
    """Segundos pedidos pela mensagem 'you have to wait N ...' (ou None)."""
    m = re.search(
        r"you\s+have\s+to\s+wait\s+(?:(\d+)\s*(minutes?|hours?|seconds?)"
        r"(?:\s*[,and]?\s*(\d+)\s*(minutes?|hours?|seconds?))?)",
        texto_puro(html), re.I)
    if not m:
        return None

    def em_segundos(num, unidade):
        u = (unidade or "").lower()
        if u.startswith("hour"):
            mult = 3600
        elif u.startswith("min"):
            mult = 60
        else:
            mult = 1
        return int(num) * mult

    total = em_segundos(m.group(1), m.group(2))
    if m.group(3):
        total += em_segundos(m.group(3), m.group(4))
    return total


def erro_rede(exc, url):
    """Mensagem amigável para falhas de rede/SSL ao falar com o site."""
    msg = f"Não consegui falar com {url} (erro de rede/SSL)."
    texto = str(exc)
    if "SSL" in texto or "TLS" in texto:
        msg += (" O servidor fechou a conexão durante o handshake TLS — "
                "pode ser bloqueio de IP (comum em IPs de datacenter) "
                "ou instabilidade temporária.")
    if len(texto) > 300:
        texto = texto[:300] + "…"
    return f"{msg} Detalhe: {texto}"


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
    # Layout novo (2025+, usado por DDownload):
    # <div id="countdown"> ... <span class="seconds">60</span> ...
    # O elemento é sinal explícito de UI; checa primeiro. (Nos layouts
    # antigos o id="countdown" costuma ser um <input value="N">, sem texto —
    # nesse caso cai nos padrões abaixo.)
    alvo = BeautifulSoup(html or "", "html.parser").find(
        id=re.compile(r"countdown", re.I))
    if alvo is not None:
        numeros = re.findall(r"\d+", alvo.get_text(" ", strip=True))
        if numeros:
            return min(int(numeros[0]), 120)
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
            elif not any(k.lower().startswith("method_") for k in campos):
                # Layout novo: o botão de download perdeu o name="method_free";
                # o servidor espera o campo para distinguir free/premium.
                campos["method_free"] = ""
            formularios.append({"action": form.get("action") or "",
                                "campos": campos})
    return formularios


def baixar_xfs(url, pasta, *, sess=None, html_inicial=None, force=False,
               nome_arquivo=None):
    """Baixa um arquivo percorrendo as etapas XFS até achar o link direto.

    ``nome_arquivo`` (opcional) força o nome do arquivo final — útil quando
    a API do site já informa o nome correto.
    """
    sess = sess or sessao()
    sess.headers["Referer"] = url

    html = html_inicial
    url_atual = url
    motivo = None          # explicação específica encontrada na página
    assinaturas = []       # para detectar páginas repetidas (loop)
    esperas_feitas = 0     # tentativas extras após "you have to wait N"

    for etapa in range(1, 8):
        if html is None:
            try:
                resp = sess.get(url_atual, timeout=CONFIG["timeout"],
                                allow_redirects=True)
            except requests.exceptions.RequestException as exc:
                raise DownloadError(erro_rede(exc, url_atual)) from exc
            if resp.status_code == 404:
                raise DownloadError(
                    "O arquivo não existe mais (HTTP 404) — "
                    "o link foi removido ou expirou.")
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                raise DownloadError(
                    f"O servidor devolveu HTTP {resp.status_code} "
                    f"ao abrir {url_atual}."
                ) from exc
            html = resp.text
            url_atual = str(resp.url)

        # 0) A página informa algum erro conhecido do XFS?
        erro = mensagem_erro(html)
        if erro:
            # Erro de "espera": o site aceita o download depois de alguns
            # minutos — aguarda e tenta de novo (máx. 2x, com teto).
            espera_seg = tempo_espera_segundos(html)
            if (espera_seg
                    and espera_seg <= int(CONFIG["max_espera_download"])
                    and esperas_feitas < 2):
                esperas_feitas += 1
                log(f"⏳ O site pediu espera de {espera_seg}s entre "
                    f"downloads. Aguardando e tentando de novo "
                    f"({esperas_feitas}/2)...")
                time.sleep(espera_seg + 2)
                html = None
                continue
            motivo = erro
            break

        # 1) Já existe link direto na página?
        for link in candidatos(html, url_atual):
            try:
                return stream_download(link, pasta, sess=sess,
                                       nome=nome_arquivo,
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
        try:
            resp = sess.post(alvo, data=formulario["campos"],
                             timeout=CONFIG["timeout"], allow_redirects=False)
        except requests.exceptions.RequestException as exc:
            raise DownloadError(erro_rede(exc, alvo)) from exc

        local = (resp.headers.get("Location") or "").strip()
        if 300 <= resp.status_code < 400 and local:
            # O XFS termina o fluxo com um redirect: o link direto vem no
            # cabeçalho Location (o corpo não é a página do próximo passo).
            proximo = urljoin(url_atual, local)
            if "op=" in proximo.lower():
                # Aponta para o passo XFS seguinte: segue o fluxo.
                html = None
                url_atual = proximo
                continue
            try:
                return stream_download(proximo, pasta, sess=sess,
                                       nome=nome_arquivo,
                                       referer=url_atual, force=force)
            except RespostaHTML:
                # Não era o arquivo: continua o fluxo a partir dessa página.
                try:
                    resp2 = sess.get(proximo, timeout=CONFIG["timeout"],
                                     allow_redirects=True)
                except requests.exceptions.RequestException as exc:
                    raise DownloadError(erro_rede(exc, proximo)) from exc
                if resp2.status_code == 404:
                    raise DownloadError(
                        "O arquivo não existe mais (HTTP 404).")
                try:
                    resp2.raise_for_status()
                except requests.exceptions.HTTPError as exc:
                    raise DownloadError(
                        f"O servidor devolveu HTTP {resp2.status_code} "
                        f"ao abrir {proximo}."
                    ) from exc
                html = resp2.text
                url_atual = str(resp2.url)
                continue
        else:
            if resp.status_code == 404:
                raise DownloadError(
                    "O arquivo não existe mais (HTTP 404).")
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                raise DownloadError(
                    f"O servidor devolveu HTTP {resp.status_code} "
                    f"na etapa {etapa} ({url_atual})."
                ) from exc
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
    NOME = "XFileSharing (Sharemods e similares)"
    DOMINIOS = DOMINIOS_XFS

    @staticmethod
    def baixar(url, pasta, force=False):
        return baixar_xfs(url, pasta, force=force)
