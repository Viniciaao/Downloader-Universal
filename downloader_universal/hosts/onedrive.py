"""OneDrive / SharePoint: links públicos de compartilhamento (1drv.ms etc.).

Usa o truque do token de compartilhamento da API pública do OneDrive:
``u!`` + URL codificada em base64url.
"""

from __future__ import annotations

import base64

from ..transfer import stream_download


class OneDrive:
    NOME = "OneDrive / SharePoint"
    DOMINIOS = {"1drv.ms", "onedrive.live.com"}

    @staticmethod
    def baixar(url, pasta, force=False):
        token = "u!" + base64.urlsafe_b64encode(url.encode()).rstrip(b"=").decode()
        direto = f"https://api.onedrive.com/v1.0/shares/{token}/root/content"
        return stream_download(direto, pasta, force=force)
