"""RapidGator via API oficial — requer conta PREMIUM.

O download gratuito do RapidGator exige captcha + espera, o que não dá para
automatizar de forma confiável. Com conta premium, a API oficial devolve um
link direto na hora.
"""

from __future__ import annotations

import re

from ..config import CONFIG
from ..transfer import DownloadError, stream_download
from ..utils import log, sessao

API = "https://rapidgator.net/api"
RE_FILE_ID = re.compile(r"/file/([A-Za-z0-9]{8,})")


class RapidGator:
    NOME = "RapidGator (premium)"
    DOMINIOS = {"rapidgator.net", "rg.to"}

    @staticmethod
    def baixar(url, pasta, force=False):
        m = RE_FILE_ID.search(url)
        if not m:
            raise DownloadError(f"Não consegui achar o id do arquivo em {url}")
        file_id = m.group(1)

        usuario = CONFIG.get("rapidgator_usuario") or ""
        senha = CONFIG.get("rapidgator_senha") or ""
        if not usuario or not senha:
            raise DownloadError(
                "O RapidGator bloqueia download automático gratuito (captcha). "
                "É preciso uma conta PREMIUM.\n"
                "Configure com: configurar(rapidgator_usuario='email', "
                "rapidgator_senha='senha')\n"
                "ou defina as variáveis de ambiente RAPIDGATOR_USER e "
                "RAPIDGATOR_PASS."
            )

        sess = sessao()
        timeout = CONFIG["timeout"]

        log("🔑 Entrando na conta RapidGator...")
        r = sess.post(f"{API}/user/login",
                      params={"username": usuario, "password": senha},
                      timeout=timeout)
        r.raise_for_status()
        dados = r.json()
        if dados.get("response_status") != 200:
            raise DownloadError(
                f"Login no RapidGator falhou (código "
                f"{dados.get('response_status')}): {dados.get('response')}. "
                "Confira usuário e senha."
            )
        sid = dados["response"]["sid"]

        log("🔎 Obtendo link direto...")
        r = sess.get(f"{API}/file/download",
                     params={"sid": sid, "file_id": file_id}, timeout=timeout)
        r.raise_for_status()
        dados = r.json()
        if dados.get("response_status") != 200:
            raise DownloadError(
                f"A API do RapidGator recusou o download (código "
                f"{dados.get('response_status')}): {dados.get('response')}. "
                "O arquivo pode ter sido removido ou sua conta não tem acesso."
            )
        link = dados["response"]["url"]

        return stream_download(link, pasta, sess=sess, referer=url, force=force)
