"""
Downloader Universal
====================

Baixa arquivos de vários sites de hospedagem — **MediaFire, Google Drive,
RapidGator (premium), Sharemods, DDownload, MEGA, OneDrive, links diretos**
e muitos outros (via motor genérico) — e move tudo para o **Google Drive**
ou para o **seu computador**.

Feito para o Google Colab, mas também funciona localmente.

Uso rápido (no Colab)::

    from downloader_universal import baixar, montar_drive, mover_para_drive

    montar_drive()
    arquivo = baixar("https://www.mediafire.com/file/XXXX/arquivo.rar/file")
    mover_para_drive(arquivo)
"""

from .config import CONFIG, configurar
from .drive_tools import (
    baixar_para_pc,
    copiar_para_drive,
    drive_montado,
    montar_drive,
    mover_para_drive,
    mover_tudo_para_drive,
    zipar,
)
from .engine import baixar, baixar_varios
from .transfer import DownloadError, stream_download

__version__ = "1.0.0"

__all__ = [
    "CONFIG",
    "configurar",
    "baixar",
    "baixar_varios",
    "baixar_para_pc",
    "copiar_para_drive",
    "drive_montado",
    "montar_drive",
    "mover_para_drive",
    "mover_tudo_para_drive",
    "zipar",
    "DownloadError",
    "stream_download",
    "__version__",
]
