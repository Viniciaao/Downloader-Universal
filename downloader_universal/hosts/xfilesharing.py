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

import re
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
    for etapa in range(1, 8):
        if html is None:
            resp = sess.get(url_atual, timeout=CONFIG["timeout"],
                            allow_redirects=True)
            resp.raise_for_status()
            html = resp.text
            url_atual = str(resp.url)

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
            break
        formulario = formularios[0]

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

    raise DownloadError(
        f"Não consegui extrair o link direto de {url}. "
        "O site pode ter mudado o formato da página, o arquivo pode ter sido "
        "removido ou pode exigir conta premium."
    )


class XFileSharing:
    NOME = "XFileSharing (Sharemods, DDownload e similares)"
    DOMINIOS = DOMINIOS_XFS

    @staticmethod
    def baixar(url, pasta, force=False):
        return baixar_xfs(url, pasta, force=force)
