"""Extratores para links diretos e sites desconhecidos (genérico).

O extrator genérico tenta, nesta ordem:
  1. A própria URL já é o arquivo (Content-Disposition / Content-Type).
  2. A página usa o motor XFileSharing (formulários ``op=download``).
  3. Caça links com cara de arquivo dentro do HTML.
  4. Último recurso: yt-dlp (que conhece centenas de sites).
"""

from __future__ import annotations

import re

import requests

from ..config import CONFIG
from ..transfer import DownloadError, RespostaHTML, stream_download
from ..utils import log, sanitizar_nome, sessao
from .xfilesharing import RE_FORM_XFS, baixar_xfs, candidatos


class Direto:
    """URL que termina com extensão de arquivo (.rar, .zip, .mp4, ...)."""

    NOME = "Link direto"
    DOMINIOS = set()

    @staticmethod
    def baixar(url, pasta, force=False):
        return stream_download(url, pasta, force=force)


def _baixar_com_ytdlp(url, pasta, force=False):
    try:
        import yt_dlp
    except ImportError:
        raise DownloadError(
            f"Não reconheci o site de {url} e o yt-dlp não está instalado "
            "para tentar como último recurso."
        )

    opcoes = {"quiet": True, "no_warnings": True, "noplaylist": True,
              "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadError(
            f"Nenhum extrator funcionou para {url}. Detalhe do yt-dlp: {exc}"
        )

    formatos = info.get("formats") or ([info] if info.get("url") else [])
    escolhido = None
    for formato in reversed(formatos):
        if formato.get("url") and str(
                formato.get("protocol", "https")).startswith("http"):
            escolhido = formato
            break
    if not escolhido:
        raise DownloadError(f"O yt-dlp não encontrou link de download em {url}.")

    nome = sanitizar_nome(info.get("title") or "")
    ext = escolhido.get("ext")
    nome_final = f"{nome}.{ext}" if (nome and ext and nome != "arquivo") else None
    return stream_download(escolhido["url"], pasta, nome=nome_final, force=force)


class Generico:
    """Qualquer outra URL: analisa a página e tenta descobrir o arquivo."""

    NOME = "Genérico (análise da página + yt-dlp)"
    DOMINIOS = set()

    @staticmethod
    def baixar(url, pasta, force=False):
        sess = sessao()
        try:
            resp = sess.get(url, timeout=CONFIG["timeout"], allow_redirects=True)
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise DownloadError(f"Não consegui abrir {url}: {exc}")

        ctype = (resp.headers.get("Content-Type") or "").lower()
        if resp.headers.get("Content-Disposition") or (
                "text/html" not in ctype
                and "application/json" not in ctype
                and "text/plain" not in ctype):
            # A própria URL já devolve o arquivo: baixa de novo, agora com
            # progresso e retomada.
            resp.close()
            return stream_download(str(resp.url), pasta, sess=sess, force=force)

        html = resp.text
        url_final = str(resp.url)

        # Página com motor XFileSharing?
        if RE_FORM_XFS.search(html) or re.search(r"\bop=download\d", html, re.I):
            return baixar_xfs(url_final, pasta, sess=sess, html_inicial=html,
                              force=force)

        # Links com cara de arquivo na página.
        log("   ↳ procurando links de arquivo na página...")
        for link in candidatos(html, url_final):
            try:
                return stream_download(link, pasta, sess=sess, referer=url_final,
                                       force=force)
            except RespostaHTML:
                continue

        # Último recurso: yt-dlp.
        log("   ↳ tentando com yt-dlp...")
        return _baixar_com_ytdlp(url_final, pasta, force=force)
