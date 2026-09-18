"""Google Drive (arquivos e pastas públicos) via gdown."""

from __future__ import annotations

import os

from ..transfer import DownloadError
from ..utils import log


class GDrive:
    NOME = "Google Drive"
    DOMINIOS = {"drive.google.com", "docs.google.com"}

    @staticmethod
    def baixar(url, pasta, force=False):
        try:
            import gdown
        except ImportError:
            raise DownloadError(
                "gdown não está instalado. Rode: pip install gdown"
            )

        os.makedirs(pasta, exist_ok=True)
        original = os.getcwd()
        os.chdir(pasta)
        try:
            if "/folders/" in url:
                log("📁 Baixando pasta do Google Drive...")
                resultado = gdown.download_folder(url, quiet=False, use_cookies=False)
            else:
                resultado = gdown.download(url, fuzzy=True, use_cookies=False)
        except DownloadError:
            raise
        except Exception as exc:
            raise DownloadError(
                f"Erro no Google Drive: {exc}\n"
                "Verifique se o compartilhamento está como "
                "'Qualquer pessoa com o link'."
            )
        finally:
            os.chdir(original)

        if not resultado:
            raise DownloadError(
                "Não consegui baixar este link do Google Drive. "
                "Confira se o arquivo está compartilhado com "
                "'Qualquer pessoa com o link'."
            )
        if isinstance(resultado, (list, tuple)):
            return [os.path.join(pasta, r) for r in resultado if r]
        return os.path.join(pasta, resultado)
