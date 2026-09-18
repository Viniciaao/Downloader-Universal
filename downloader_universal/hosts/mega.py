"""MEGA (suporte opcional — requer `pip install mega.py`)."""

from __future__ import annotations

import os

from ..transfer import DownloadError
from ..utils import log


class MegaHost:
    NOME = "MEGA"
    DOMINIOS = {"mega.nz", "mega.co.nz"}

    @staticmethod
    def baixar(url, pasta, force=False):
        if "/folder" in url:
            raise DownloadError(
                "Pastas do MEGA não são suportadas. "
                "Cole o link de cada arquivo individualmente."
            )
        try:
            from mega import Mega
        except ImportError:
            raise DownloadError(
                "Suporte ao MEGA não instalado. Rode: pip install mega.py "
                "(opcional) e tente de novo."
            )

        os.makedirs(pasta, exist_ok=True)
        log("🔑 Conectando ao MEGA (login anônimo)...")
        try:
            mega = Mega().login()
            try:
                return mega.download_url(url, dest_path=pasta, is_public_url=True)
            except TypeError:
                return mega.download_url(url, dest_path=pasta)
        except DownloadError:
            raise
        except Exception as exc:
            raise DownloadError(
                f"Erro no MEGA: {exc}\n"
                "O link pode exigir chave de descriptografia ou ter sido removido."
            )
