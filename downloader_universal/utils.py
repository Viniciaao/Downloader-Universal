"""Utilidades HTTP e de arquivos para o Downloader Universal."""

from __future__ import annotations

import os
import re
import unicodedata
from urllib.parse import unquote, urlparse

import requests

from .config import CONFIG

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

#: Extensões reconhecidas como "arquivo" (usadas para detectar links diretos).
EXTENSOES_ARQUIVO = {
    ".7z", ".apk", ".avi", ".bin", ".bz2", ".cue", ".deb", ".dmg", ".doc",
    ".docx", ".epub", ".exe", ".flac", ".gba", ".gif", ".gz", ".iso", ".jar",
    ".jpeg", ".jpg", ".m4a", ".mdf", ".mds", ".mkv", ".mov", ".mp3", ".mp4",
    ".mpg", ".msi", ".nds", ".nsp", ".ogg", ".ova", ".ovf", ".pdf", ".png",
    ".ppt", ".pptx", ".rar", ".rpm", ".tar", ".txt", ".wav", ".webm",
    ".webp", ".wma", ".wmv", ".xci", ".xls", ".xlsx", ".xz", ".zip", ".zst",
}


def sessao() -> requests.Session:
    """Cria uma sessão HTTP com cabeçalhos de navegador."""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return s


def log(mensagem: str) -> None:
    """Imprime mensagem de status (respeita CONFIG['verbose'])."""
    if CONFIG.get("verbose", True):
        print(mensagem, flush=True)


def dominio(url: str) -> str:
    """Retorna o domínio da URL, sem 'www.' e sem porta."""
    netloc = urlparse(url).netloc.lower().split(":")[0]
    return netloc[4:] if netloc.startswith("www.") else netloc


def sanitizar_nome(nome: str) -> str:
    """Remove caracteres inválidos para nome de arquivo e limita o tamanho."""
    if not nome:
        return ""
    nome = unquote(nome)
    nome = unicodedata.normalize("NFC", nome)
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome).strip(" .")
    return nome[:180] or "arquivo"


def nome_arquivo_da_resposta(resp, url: str) -> str:
    """Descobre o nome do arquivo via Content-Disposition ou pela URL."""
    cd = (resp.headers or {}).get("Content-Disposition", "") or ""
    m = re.search(r"filename\*\s*=\s*(?:[Uu][Tt][Ff]-8)?'?'?([^;]+)", cd)
    if m:
        nome = sanitizar_nome(m.group(1))
        if nome and nome != "arquivo":
            return nome
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd)
    if m:
        nome = sanitizar_nome(m.group(1))
        if nome and nome != "arquivo":
            return nome
    base = os.path.basename(urlparse(url).path)
    return sanitizar_nome(base) or "arquivo"


def parece_link_direto(url: str) -> bool:
    """True se a URL termina com uma extensão de arquivo conhecida."""
    caminho = urlparse(url).path.lower()
    return any(caminho.endswith(ext) for ext in EXTENSOES_ARQUIVO)


def tamanho_humano(num) -> str:
    """Formata bytes em formato legível (ex.: '345.7 MB')."""
    try:
        num = float(num)
    except (TypeError, ValueError):
        return ""
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            if unidade == "B":
                return f"{int(num)} B"
            return f"{num:.1f} {unidade}"
        num /= 1024
    return f"{num:.1f} PB"
