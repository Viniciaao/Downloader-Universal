"""Registro de extratores: escolhe o certo para cada URL."""

from __future__ import annotations

from ..utils import dominio, parece_link_direto
from .ddownload import DDownload
from .generico import Direto, Generico
from .gdrive import GDrive
from .mediafire import MediaFire
from .mega import MegaHost
from .onedrive import OneDrive
from .rapidgator import RapidGator
from .xfilesharing import XFileSharing

#: Ordem de prioridade: hosts específicos primeiro.
#: (DDownload antes de XFileSharing: usa a API pública + o motor XFS.)
EXTRATORES = [
    MediaFire, GDrive, RapidGator, MegaHost, OneDrive, DDownload,
    XFileSharing,
]


def detectar(url: str):
    """Devolve a classe do extrator apropriado para a URL."""
    dom = dominio(url)
    for cls in EXTRATORES:
        for d in cls.DOMINIOS:
            if dom == d or dom.endswith("." + d):
                return cls
    if parece_link_direto(url):
        return Direto
    return Generico
