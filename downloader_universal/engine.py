"""Funções principais: baixar um link ou vários, com detecção automática do site."""

from __future__ import annotations

from . import hosts
from .config import CONFIG
from .transfer import DownloadError
from .utils import log


def baixar(url, pasta=None, force=False):
    """Baixa um arquivo (ou pasta) de qualquer URL suportada.

    Retorna o caminho do arquivo baixado (ou uma lista de caminhos, no caso
    de pastas do MediaFire/Google Drive).

    Exemplo::

        caminho = baixar("https://www.mediafire.com/file/XXXX/arquivo.rar/file")
    """
    url = (url or "").strip()
    if not url:
        raise DownloadError("URL vazia.")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url

    pasta = pasta or CONFIG["pasta_downloads"]
    extrator = hosts.detectar(url)
    log(f"🔎 {url}\n   ↳ site detectado: {extrator.NOME}")
    return extrator.baixar(url, pasta, force=force)


def baixar_varios(urls, pasta=None, force=False):
    """Baixa vários links de uma vez, sem parar nos erros.

    ``urls`` pode ser uma lista ou um texto com um link por linha.
    Retorna uma lista de dicionários com o resultado de cada link::

        [{"url": ..., "ok": True,  "arquivos": [...]},
         {"url": ..., "ok": False, "erro": "..."}]
    """
    if isinstance(urls, str):
        urls = [linha.strip() for linha in urls.strip().splitlines()]

    resultados = []
    validas = [u for u in urls if u and not u.startswith("#")]
    total = len(validas)
    for i, url in enumerate(validas, 1):
        log(f"\n[{i}/{total}] Processando...")
        try:
            resultado = baixar(url, pasta=pasta, force=force)
            arquivos = resultado if isinstance(resultado, (list, tuple)) else [resultado]
            resultados.append({"url": url, "ok": True, "arquivos": arquivos})
        except Exception as exc:  # noqa: BLE001 - queremos continuar nos outros
            log(f"❌  Erro: {exc}")
            resultados.append({"url": url, "ok": False, "erro": str(exc)})

    ok = sum(1 for r in resultados if r["ok"])
    log(f"\n📊 Resumo: {ok}/{total} downloads concluídos.")
    if ok < total:
        for r in resultados:
            if not r["ok"]:
                log(f"   ❌ {r['url']}\n      motivo: {r['erro']}")
    return resultados
