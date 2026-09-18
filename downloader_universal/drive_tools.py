"""Integração com o Google Drive (Colab) e envio de arquivos para o seu PC."""

from __future__ import annotations

import os
import shutil

from .config import CONFIG
from .utils import log

PONTO_MONTAGEM = "/content/drive"
RAIZ_DRIVE = os.path.join(PONTO_MONTAGEM, "MyDrive")


def drive_montado():
    """True se o Google Drive está montado no Colab."""
    return os.path.isdir(RAIZ_DRIVE)


def montar_drive():
    """Monta o Google Drive no Colab (pede autorização no navegador)."""
    if drive_montado():
        log("✅ Google Drive já está montado em /content/drive")
        return RAIZ_DRIVE
    try:
        from google.colab import drive
    except ImportError:
        raise RuntimeError(
            "montar_drive() só funciona dentro do Google Colab. "
            "Fora do Colab, os arquivos já ficam no seu computador."
        )
    drive.mount(PONTO_MONTAGEM)
    log("✅ Google Drive montado em /content/drive")
    return RAIZ_DRIVE


def _destino_drive(pasta_drive):
    if not drive_montado():
        raise RuntimeError(
            "O Google Drive não está montado. Rode montar_drive() antes."
        )
    destino = os.path.join(RAIZ_DRIVE, pasta_drive)
    os.makedirs(destino, exist_ok=True)
    return destino


def _nome_unico(destino_dir, nome):
    alvo = os.path.join(destino_dir, nome)
    if not os.path.exists(alvo):
        return alvo
    base, ext = os.path.splitext(nome)
    i = 1
    while True:
        candidato = os.path.join(destino_dir, f"{base} ({i}){ext}")
        if not os.path.exists(candidato):
            return candidato
        i += 1


def _iterar(origem):
    if isinstance(origem, (list, tuple)):
        return list(origem)
    return [origem]


def mover_para_drive(origem, pasta_drive="Downloader Universal"):
    """Move arquivo/pasta (ou lista deles) do Colab para o seu Google Drive.

    Exemplo::

        mover_para_drive("downloads/arquivo.rar", pasta_drive="Meus Downloads")
    """
    destino_dir = _destino_drive(pasta_drive)
    movidos = []
    for item in _iterar(origem):
        if not os.path.exists(item):
            log(f"⚠️  Não existe: {item} (ignorado)")
            continue
        alvo = _nome_unico(destino_dir, os.path.basename(item.rstrip("/")))
        shutil.move(item, alvo)
        movidos.append(alvo)
        log(f"📤 Movido para o Drive: {alvo}")
    return movidos[0] if len(movidos) == 1 else movidos


def copiar_para_drive(origem, pasta_drive="Downloader Universal"):
    """Igual a mover_para_drive, mas mantém uma cópia no Colab."""
    destino_dir = _destino_drive(pasta_drive)
    copiados = []
    for item in _iterar(origem):
        if not os.path.exists(item):
            log(f"⚠️  Não existe: {item} (ignorado)")
            continue
        alvo = _nome_unico(destino_dir, os.path.basename(item.rstrip("/")))
        if os.path.isdir(item):
            shutil.copytree(item, alvo)
        else:
            shutil.copy2(item, alvo)
        copiados.append(alvo)
        log(f"📤 Copiado para o Drive: {alvo}")
    return copiados[0] if len(copiados) == 1 else copiados


def mover_tudo_para_drive(pasta=None, pasta_drive="Downloader Universal"):
    """Move tudo que está na pasta de downloads para o Google Drive."""
    pasta = pasta or CONFIG["pasta_downloads"]
    if not os.path.isdir(pasta):
        raise FileNotFoundError(f"Pasta de downloads não existe: {pasta}")
    itens = [os.path.join(pasta, n) for n in sorted(os.listdir(pasta))
             if not n.endswith(".part")]
    if not itens:
        log("ℹ️  A pasta de downloads está vazia, nada para mover.")
        return []
    return mover_para_drive(itens, pasta_drive=pasta_drive)


def zipar(caminho, nome_zip=None):
    """Compacta um arquivo ou pasta em .zip (útil antes de baixar para o PC).

    Retorna o caminho do .zip criado.
    """
    if not os.path.exists(caminho):
        raise FileNotFoundError(caminho)
    nome_zip = nome_zip or os.path.basename(caminho.rstrip("/"))
    log(f"🗜️  Compactando {caminho} ...")
    return shutil.make_archive(nome_zip, "zip",
                               root_dir=os.path.dirname(os.path.abspath(caminho)) or ".",
                               base_dir=os.path.basename(caminho.rstrip("/")))


def baixar_para_pc(caminho):
    """Envia o arquivo do Colab para o seu computador (download no navegador).

    Dica: para arquivos muito grandes (> ~1 GB), use zipar() antes.
    """
    try:
        from google.colab import files
    except ImportError:
        raise RuntimeError(
            "baixar_para_pc() só funciona dentro do Google Colab. "
            "Fora do Colab, o arquivo já está salvo no seu computador."
        )
    itens = _iterar(caminho)
    for item in itens:
        if os.path.isdir(item):
            raise ValueError(
                f"{item} é uma pasta — use zipar('{item}') antes de baixar."
            )
        if not os.path.isfile(item):
            raise FileNotFoundError(item)
    for item in itens:
        log(f"💻 Enviando para o seu computador: {item}")
        files.download(item)
    return itens[0] if len(itens) == 1 else itens
