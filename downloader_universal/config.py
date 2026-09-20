"""Configuração global do Downloader Universal."""

from __future__ import annotations

import os

#: Opções globais. Altere com :func:`configurar`.
CONFIG = {
    # Pasta onde os arquivos são salvos (relativa ao diretório atual).
    "pasta_downloads": "downloads",
    # Conta RapidGator (precisa ser PREMIUM para download automático).
    # Também podem ser definidas pelas variáveis de ambiente
    # RAPIDGATOR_USER e RAPIDGATOR_PASS.
    "rapidgator_usuario": os.environ.get("RAPIDGATOR_USER", ""),
    "rapidgator_senha": os.environ.get("RAPIDGATOR_PASS", ""),
    # Timeout (segundos) para requisições de página.
    "timeout": 30,
    # Tentativas de download em caso de queda de conexão.
    "retries": 3,
    # Teto (segundos) para espera de "cooldown" entre downloads gratuitos
    # ("You have to wait N ..."): o programa aguarda e tenta de novo
    # sozinho, no máximo 2 vezes.
    "max_espera_download": 180,
    # Mostra mensagens de status.
    "verbose": True,
}


def configurar(**kwargs):
    """Atualiza as opções globais.

    Exemplo::

        configurar(pasta_downloads="meus_arquivos",
                   rapidgator_usuario="email@exemplo.com",
                   rapidgator_senha="senha")

    Retorna uma cópia da configuração atual.
    """
    desconhecidas = sorted(set(kwargs) - set(CONFIG))
    if desconhecidas:
        raise ValueError(
            f"Opções desconhecidas: {desconhecidas}. "
            f"Opções válidas: {sorted(CONFIG)}"
        )
    CONFIG.update(kwargs)
    return dict(CONFIG)
