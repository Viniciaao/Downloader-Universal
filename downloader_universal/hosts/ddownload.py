"""Extrator dedicado do DDownload.com (ex-dll.to).

O DDownload é um site XFileSharing "de roupa nova" (reescrito em 2025):

  1. A página do arquivo mostra uma verificação Cloudflare Turnstile;
  2. Depois, um contador de ~60s ("Please wait before downloading");
  3. Em seguida, um formulário XFS clássico (op=download1 -> download2 -> ...);
  4. O passo final termina com um redirect (cabeçalho Location) para o
     link direto do arquivo.

Este módulo:

  * lê o **código do arquivo** (12 caracteres) da URL;
  * consulta a **API pública** do DDownload
    (``https://api-v2.ddownload.com/api``) para pré-ler metadados
    (nome/tamanho/status) e falhar cedo com uma mensagem clara quando o
    arquivo foi removido ou bloqueado por DMCA;
  * percorre o fluxo de página via :func:`baixar_xfs` (motor XFS);
  * quando há bloqueio por captcha/contador, orienta a concluir o download
    no navegador, sem prometer suporte premium ou resolução automática.

A chave da API pública é a mesma usada pelo plugin do pyLoad
(``DdownloadCom``) — serve apenas para consultar metadados de arquivos
públicos, sem conta. O download em si continua passando pela página.
"""

from __future__ import annotations

import re

import requests

from ..config import CONFIG
from ..transfer import DownloadError
from ..utils import log, sanitizar_nome, sessao, tamanho_humano, dominio
from .xfilesharing import baixar_xfs

#: Domínios do DDownload (o ddl.to é o domínio antigo, ainda redireciona).
DOMINIOS = {
    "ddownload.com",
    "ddl.to",
    "api.ddl.to",
}

API_BASE = "https://api-v2.ddownload.com/api"

#: Chave pública usada pelo pyLoad para consultar a API de arquivos públicos.
#: Uso aqui: apenas metadados (nome/tamanho/status) — o download não
#: depende dela e segue funcionando se a API mudar de lugar.
API_CHAVE_PUBLICA = "37699zuaj90n9hxado2m7"

#: URL do tipo https://ddownload.com/<código de 12 letras e números>[/nome]
RE_CODIGO = re.compile(r"/([a-z0-9]{12})(?:/[^/?#]*)?(?:[?#]|$)", re.I)

DICA_VERIFICACAO = (
    "O download gratuito do DDownload pode exigir captcha e espera. "
    "Este projeto não resolve desafios de navegador automaticamente.\n"
    "Abra o link original no navegador e conclua o download por lá. "
    "Rodar em uma conexão residencial pode mudar a resposta do site, "
    "mas não garante que o captcha desapareça.\n"
    "A consulta à API pública só lê metadados: ela não libera o download. "
    "Este projeto ainda não implementa autenticação premium do DDownload."
)

DICA_TURNSTILE = (
    "A página exige Cloudflare Turnstile, que precisa de um navegador "
    "para executar a verificação.\n" + DICA_VERIFICACAO
)


def extrair_codigo(url):
    """Código do arquivo (12 caracteres) extraído da URL, ou None."""
    m = RE_CODIGO.search(url or "")
    return m.group(1).lower() if m else None


def info_arquivo(sess, codigo):
    """Metadados do arquivo pela API pública (melhor esforço).

    Retorna o dicionário do arquivo (com ``name``, ``size``, ``status``,
    ``uploaded`` ...) ou ``None`` se a API estiver inacessível — o fluxo
    de download continua pela página mesmo sem ela.
    """
    try:
        resp = sess.get(
            f"{API_BASE}/file/info",
            params={"key": API_CHAVE_PUBLICA, "file_code": codigo},
            timeout=min(int(CONFIG["timeout"]), 15),
        )
        dados = resp.json()
    except (requests.exceptions.RequestException, ValueError, TypeError):
        return None

    if not isinstance(dados, dict):
        return None
    result = dados.get("result")
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and str(item.get("filecode", "")).lower() == codigo:
                return item
            if isinstance(item, dict) and item.get("name"):
                return item
    return None


def _erro_de_status_api(item):
    """Erro amigável se a API disser que o arquivo está indisponível."""
    status = item.get("status")
    if status == 404:
        return ("O arquivo não existe mais no DDownload "
                "(removido pelo dono, expirado por inatividade ou "
                "link inválido).")
    if status == 451:
        return "O arquivo foi removido por direitos autorais (DMCA)."
    return None


class DDownload:
    """DDownload.com (ex-dll.to): API pública + fluxo XFS da página."""

    NOME = "DDownload (ex-dll.to)"
    DOMINIOS = DOMINIOS

    @staticmethod
    def baixar(url, pasta, force=False):
        codigo = extrair_codigo(url)
        if not codigo:
            raise DownloadError(
                f"URL de DDownload inválida — não encontrei o código do "
                f"arquivo (12 letras/números): {url}"
            )

        sess = sessao()
        # Idioma fixo evita a página intermediária de seleção de idioma.
        sess.cookies.set("lang", "english", domain=dominio(url))

        # 1) Pré-leitura pela API pública (melhor esforço).
        info = info_arquivo(sess, codigo)
        if info is not None:
            erro_api = _erro_de_status_api(info)
            if erro_api:
                raise DownloadError(erro_api)
            nome = info.get("name")
            if nome:
                extra = tamanho_humano(info.get("size"))
                quando = info.get("uploaded")
                log("📄 " + nome
                    + (f" ({extra})" if extra else "")
                    + (f" — enviado em {quando}" if quando else ""))
        else:
            log("⚠️  API do DDownload inacessível; seguindo direto pela página.")

        nome_arquivo = sanitizar_nome(info.get("name")) if info and info.get("name") else None

        # 2) Fluxo de página (XFS: contador, formulários, redirect final).
        try:
            return baixar_xfs(url, pasta, sess=sess, force=force,
                              nome_arquivo=nome_arquivo)
        except DownloadError as exc:
            msg = str(exc)
            if "Turnstile" in msg:
                raise DownloadError(f"{msg}\n\n💡 {DICA_TURNSTILE}") from exc
            if "captcha" in msg.lower() or "contagem regressiva" in msg.lower():
                raise DownloadError(f"{msg}\n\n💡 {DICA_VERIFICACAO}") from exc
            raise
