"""Núcleo de transferência: download com retomada, progresso e retentativas."""

from __future__ import annotations

import os
import time

import requests

from .config import CONFIG
from .utils import log, nome_arquivo_da_resposta, sessao, tamanho_humano

CHUNK = 256 * 1024  # 256 KB por leitura


class DownloadError(RuntimeError):
    """Erro ao resolver o link ou baixar o arquivo."""


class RespostaHTML(DownloadError):
    """A URL devolveu uma página HTML em vez do arquivo."""


class _ProgressoSimples:
    """Barra de progresso em texto puro (fallback quando tqdm não existe)."""

    def __init__(self, total, descricao=""):
        self.total = total or 0
        self.visto = 0
        self.descricao = descricao or "download"
        self._ultimo_pct = -10

    def update(self, n):
        self.visto += n
        if not self.total:
            return
        pct = int(self.visto * 100 / self.total)
        if pct >= self._ultimo_pct + 10:
            self._ultimo_pct = pct
            log(f"  {self.descricao[:50]}: {pct}% de {tamanho_humano(self.total)}")

    def close(self):
        pass


def _barra_progresso(total, descricao):
    try:
        from tqdm.auto import tqdm

        return tqdm(total=total, unit="B", unit_scale=True, desc=descricao[:50],
                    leave=True, mininterval=0.5)
    except Exception:
        return _ProgressoSimples(total, descricao)


def stream_download(url, pasta, *, sess=None, nome=None, referer=None,
                    cabecalhos=None, force=False):
    """Baixa ``url`` para ``pasta`` com retomada, progresso e retentativas.

    Retorna o caminho final do arquivo. Se o arquivo já existir completo,
    o download é pulado (use ``force=True`` para baixar de novo).
    """
    sess = sess or sessao()
    os.makedirs(pasta, exist_ok=True)
    hdrs = dict(cabecalhos or {})
    if referer:
        hdrs["Referer"] = referer

    ultimo_erro = None
    for tentativa in range(1, int(CONFIG["retries"]) + 1):
        try:
            return _baixar_uma_vez(url, pasta, sess, nome, hdrs, force)
        except RespostaHTML:
            raise
        except requests.exceptions.HTTPError as exc:
            codigo = exc.response.status_code if exc.response is not None else 0
            if 400 <= codigo < 500:
                raise DownloadError(
                    f"O servidor recusou o download (HTTP {codigo}) para: {url}"
                ) from exc
            ultimo_erro = exc
        except (requests.exceptions.RequestException, OSError) as exc:
            ultimo_erro = exc
        if tentativa < int(CONFIG["retries"]):
            espera = 3 * tentativa
            log(f"⚠️  Falha na tentativa {tentativa}/{CONFIG['retries']}: "
                f"{ultimo_erro}. Nova tentativa em {espera}s...")
            time.sleep(espera)
    raise DownloadError(
        f"Download falhou após {CONFIG['retries']} tentativas: {ultimo_erro}"
    )


def _baixar_uma_vez(url, pasta, sess, nome, hdrs, force):
    headers = dict(hdrs)
    timeout = CONFIG["timeout"]

    resp = sess.get(url, headers=headers, stream=True, timeout=timeout,
                    allow_redirects=True)
    try:
        nome_final = nome or nome_arquivo_da_resposta(resp, resp.url)
        destino = os.path.join(pasta, nome_final)

        if not force and os.path.isfile(destino) and os.path.getsize(destino) > 0:
            log(f"✅  Já existe: {destino} (pulado). Use force=True para baixar de novo.")
            return destino

        parcial = destino + ".part"
        if force and os.path.exists(parcial):
            os.remove(parcial)
        ja_tem = os.path.getsize(parcial) if os.path.isfile(parcial) else 0

        # Retomada: se já existe um pedaço, pede só o restante (RFC 7233).
        if ja_tem > 0 and not headers.get("Range"):
            resp.close()
            headers["Range"] = f"bytes={ja_tem}-"
            log(f"↩️  Retomando download de {nome_final} a partir de "
                f"{tamanho_humano(ja_tem)}...")
            resp = sess.get(url, headers=headers, stream=True, timeout=timeout,
                            allow_redirects=True)

        if resp.status_code == 416:
            # O servidor disse que já temos tudo.
            if ja_tem > 0:
                os.replace(parcial, destino)
                log(f"✅  {destino} concluído (a parte existente estava completa).")
                return destino
            raise DownloadError(f"Servidor retornou HTTP 416 para {url}.")
        resp.raise_for_status()

        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "text/html" in ctype and not nome_final.lower().endswith((".html", ".htm")):
            raise RespostaHTML(
                f"A URL devolveu uma página HTML em vez de um arquivo: {url}"
            )

        modo = "ab" if (resp.status_code == 206 and ja_tem > 0) else "wb"
        if modo == "wb" and os.path.exists(parcial):
            os.remove(parcial)
            ja_tem = 0

        total = None
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit():
            total = int(cl) + (ja_tem if modo == "ab" else 0)

        log(f"⬇️  Baixando {nome_final}"
            + (f" ({tamanho_humano(total)})" if total else ""))
        barra = _barra_progresso(total, nome_final)
        try:
            with open(parcial, modo) as f:
                for pedaco in resp.iter_content(chunk_size=CHUNK):
                    if pedaco:
                        f.write(pedaco)
                        barra.update(len(pedaco))
        finally:
            barra.close()
    finally:
        resp.close()

    os.replace(parcial, destino)
    log(f"✅  Salvo em: {destino}")
    return destino
