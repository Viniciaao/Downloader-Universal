"""MediaFire: arquivos e pastas, sem precisar de conta."""

from __future__ import annotations

import html as _html
import re

from ..config import CONFIG
from ..transfer import DownloadError, stream_download
from ..utils import log, sessao

PADROES_LINK = [
    # Botão de download oficial da página.
    re.compile(r'<a[^>]*id=["\']downloadButton["\'][^>]*href=["\']([^"\']+)["\']', re.I),
    re.compile(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*id=["\']downloadButton["\']', re.I),
    re.compile(r'aria-label=["\']Download file["\'][^>]*href=["\']([^"\']+)["\']', re.I),
    re.compile(r'href=["\']([^"\']+)["\'][^>]*aria-label=["\']Download file["\']', re.I),
    # Qualquer link para os servidores de download/CDN do MediaFire.
    re.compile(r'href=["\'](https?://download\d*\.mediafire\.com/[^"\']+)["\']', re.I),
    re.compile(r'href=["\'](https?://cdn\d*\.mediafire\.com/[^"\']+)["\']', re.I),
    re.compile(r'["\'](https?://(?:download|cdn)\d+\.mediafire\.com/[^"\'\s]+)["\']', re.I),
]

RE_LINK_ARQUIVO = re.compile(
    r'href="(https?://(?:www\.)?mediafire\.com/file/[^"/]+/[^"]+?)/file"', re.I
)


def _extrair_link(html: str):
    for padrao in PADROES_LINK:
        m = padrao.search(html)
        if m:
            return _html.unescape(m.group(1)).strip()
    return None


class MediaFire:
    NOME = "MediaFire"
    DOMINIOS = {"mediafire.com"}

    @staticmethod
    def baixar(url, pasta, force=False):
        sess = sessao()
        if "/folder/" in url:
            return MediaFire.baixar_pasta(url, pasta, force=force)

        resp = sess.get(url, timeout=CONFIG["timeout"], allow_redirects=True)
        resp.raise_for_status()
        html = resp.text

        link = _extrair_link(html)
        if not link:
            if re.search(r"(invalid link|file (was )?not found|error\b)", html, re.I):
                raise DownloadError(
                    "O arquivo do MediaFire não existe mais (link inválido/removido)."
                )
            raise DownloadError(
                "Não encontrei o link direto na página do MediaFire. "
                "O site pode ter mudado ou o arquivo pode exigir verificação."
            )
        return stream_download(link, pasta, sess=sess, referer=str(resp.url),
                               force=force)

    @staticmethod
    def baixar_pasta(url, pasta, force=False):
        """Baixa todos os arquivos de uma pasta pública do MediaFire."""
        sess = sessao()
        resp = sess.get(url, timeout=CONFIG["timeout"], allow_redirects=True)
        resp.raise_for_status()

        links = []
        for m in RE_LINK_ARQUIVO.finditer(resp.text):
            link = m.group(1) + "/file"
            if link not in links:
                links.append(link)
        if not links:
            raise DownloadError(
                "Não encontrei arquivos nessa pasta do MediaFire "
                "(ela pode ser privada ou ter sido removida)."
            )

        log(f"📁 Pasta do MediaFire com {len(links)} arquivo(s).")
        caminhos = []
        for i, link in enumerate(links, 1):
            log(f"\n[{i}/{len(links)}] {link}")
            try:
                caminhos.append(MediaFire.baixar(link, pasta, force=force))
            except DownloadError as exc:
                log(f"❌  Erro: {exc}")
        return caminhos
