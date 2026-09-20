#!/usr/bin/env python3
"""Gera o arquivo Downloader_Universal.ipynb (executar uma única vez)."""

import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))


def md(*linhas):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [l if l == "\n" else l for l in linhas],
    }


def code(*linhas):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": linhas,
    }


celulas = [
    md(
        "# 📥 Downloader Universal\n",
        "\n",
        "Baixa arquivos de **MediaFire, Google Drive, RapidGator, Sharemods, DDownload, MEGA, OneDrive**, links diretos e vários outros sites — e depois move tudo para o seu **Google Drive** ☁️ ou para o **seu computador** 💻.\n",
        "\n",
        "**Como usar:** rode as células em ordem (menu *Runtime ▸ Run all* ou Shift+Enter em cada uma).\n",
        "\n",
        "> 📖 Documentação completa: [github.com/Viniciaao/Downloader-Universal](https://github.com/Viniciaao/Downloader-Universal)\n",
    ),
    code(
        '# ⚙️ 1. SETUP — instale/atualize o projeto\n',
        'import os, subprocess, sys\n',
        'from pathlib import Path\n',
        '\n',
        'repo = Path("/content/Downloader-Universal")\n',
        'if (repo / ".git").is_dir():\n',
        '    subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"], check=True)\n',
        'else:\n',
        '    subprocess.run(["git", "clone", "https://github.com/Viniciaao/Downloader-Universal.git", str(repo)], check=True)\n',
        'os.chdir(repo)\n',
        'subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)\n',
        '\n',
        '# git pull atualiza os arquivos, mas não os módulos já importados no Python.\n',
        'if any(n == "downloader_universal" or n.startswith("downloader_universal.") for n in sys.modules):\n',
        '    raise RuntimeError("Projeto atualizado no disco. Use Ambiente de execução > Reiniciar sessão (não excluir) e rode as células novamente para carregar o código novo. Isso redefine as configurações em memória.")\n',
        'if str(repo) not in sys.path:\n',
        '    sys.path.insert(0, str(repo))\n',
        '\n',
        "from downloader_universal import (baixar, baixar_varios, configurar,\n",
        "                                  montar_drive, mover_para_drive,\n",
        "                                  copiar_para_drive, mover_tudo_para_drive,\n",
        "                                  baixar_para_pc, zipar)\n",
        "print('✅ Tudo pronto! Pode rodar as próximas células.')\n",
    ),
    md(
        "## 🔗 2. Conectar ao Google Drive (opcional)\n",
        "\n",
        "Se você quer **guardar os arquivos no Google Drive**, deixe `conectar_drive` ligado e rode a célula — o Google vai pedir autorização.\n",
        "\n",
        "Se prefere **baixar direto para o seu notebook**, pode pular esta etapa.\n",
    ),
    code(
        "# @markdown ### Conectar ao Google Drive\n",
        "conectar_drive = True  # @param {type:\"boolean\"}\n",
        "\n",
        "# @markdown ### RapidGator (opcional)\n",
        "# @markdown O RapidGator só libera download automático com **conta premium**:\n",
        "rapidgator_usuario = \"\"  # @param {type:\"string\"}\n",
        "rapidgator_senha = \"\"  # @param {type:\"string\"}\n",
        "\n",
        "configurar(rapidgator_usuario=rapidgator_usuario,\n",
        "           rapidgator_senha=rapidgator_senha)\n",
        "\n",
        "if conectar_drive:\n",
        "    montar_drive()\n",
        "else:\n",
        "    print('👌 Drive não conectado — os downloads ficarão disponíveis para baixar para o seu PC.')\n",
    ),
    md(
        "## ⬇️ 3. Baixar um link\n",
        "\n",
        "Cole a URL de qualquer site suportado (MediaFire, Google Drive, Sharemods, DDownload, RapidGator premium, MEGA, OneDrive, link direto...).\n",
        "\n",
        "> **DDownload:** o log deve mostrar `DDownload (ex-dll.to)`. Se aparecer `XFileSharing`, atualize pelo SETUP e reinicie a sessão para descartar o código antigo. Se houver captcha, conclua o download no navegador; a API pública não elimina a verificação.\n",
    ),
    code(
        "url = \"https://www.mediafire.com/file/4srp1nshasmcj0y/Drag2onBa2llXeno2ver2se-Update1.25.01-elamigos.rar/file\"  # @param {type:\"string\"}\n",
        "\n",
        "arquivo = baixar(url)\n",
        "print('\\n🎉 Baixado:', arquivo)\n",
    ),
    md(
        "## ⬇️ 4. Baixar vários links de uma vez\n",
        "\n",
        "Cole **um link por linha**. Se algum falhar, os outros continuam normalmente.\n",
    ),
    code(
        "# Cole um link por linha entre as aspas triplas:\n",
        "links = \"\"\"\n",
        "https://www.mediafire.com/file/xxxx/exemplo.rar/file\n",
        "https://sharemods.com/abcdef/mod.zip.html\n",
        "\"\"\"\n",
        "\n",
        "resultados = baixar_varios(links)\n",
        "\n",
        "# junta todos os arquivos baixados numa lista só:\n",
        "arquivos = [a for r in resultados if r['ok'] for a in r['arquivos']]\n",
        "print('\\n📂 Arquivos baixados:'); [print('  -', a) for a in arquivos]\n",
    ),
    md(
        "## ☁️ 5. Mover para o Google Drive\n",
        "\n",
        "Os arquivos ficam salvos em `downloads/` dentro do Colab. Mova para o seu Drive para não perdê-los quando a sessão fechar.\n",
    ),
    code(
        "pasta_no_drive = \"Downloader Universal\"  # @param {type:\"string\"}\n",
        "# @markdown Com `mover_tudo` ligado, move todos os arquivos da pasta de downloads:\n",
        "mover_tudo = True  # @param {type:\"boolean\"}\n",
        "\n",
        "if mover_tudo:\n",
        "    mover_tudo_para_drive(pasta_drive=pasta_no_drive)\n",
        "else:\n",
        "    mover_para_drive(arquivo, pasta_drive=pasta_no_drive)  # usa o arquivo da célula 3\n",
    ),
    md(
        "## 💻 6. Baixar para o seu computador\n",
        "\n",
        "Prefere o arquivo no seu notebook? A célula abaixo abre o download no navegador.\n",
        "\n",
        "> 💡 Para arquivos muito grandes (mais de ~1 GB), use `zipar(arquivo)` antes.\n",
    ),
    code(
        "baixar_para_pc(arquivo)   # arquivo da célula 3\n",
        "# ou: baixar_para_pc(arquivos)  para vários arquivos da célula 4\n",
    ),
    md(
        "---\n",
        "## 🌐 Sites suportados\n",
        "\n",
        "| Site | Status | Observações |\n",
        "|---|---|---|\n",
        "| MediaFire | ✅ | arquivos e pastas, sem conta |\n",
        "| Google Drive | ✅ | arquivos e pastas públicos |\n",
        "| Sharemods | ✅ | download grátis, espera automática |\n",
        "| DDownload (ex-dll.to) | 🔶 | API de metadados + fluxo XFS; captchas exigem navegador. Sem garantia em IP residencial e sem autenticação premium implementada |\n",
        "| RapidGator | 🔶 | requer conta **premium** |\n",
        "| MEGA | ✅* | `!pip install mega.py` (opcional) |\n",
        "| OneDrive / 1drv.ms | ✅ | links públicos |\n",
        "| Sites XFS em geral | ✅ | detectados automaticamente |\n",
        "| Links diretos | ✅ | `.rar`, `.zip`, `.7z`, `.iso`, `.mp4`, ... |\n",
        "| Outros | 🔶 | análise da página + yt-dlp |\n",
        "\n",
        "⚖️ **Aviso:** use apenas com arquivos que você tem direito de baixar. Respeite os termos dos sites e as leis de direitos autorais.\n",
    ),
]

notebook = {
    "cells": celulas,
    "metadata": {
        "colab": {"name": "Downloader Universal", "provenance": [], "toc_visible": True},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

saida = os.path.join(os.path.dirname(AQUI), "Downloader_Universal.ipynb")
with open(saida, "w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)
    f.write("\n")
print("Gerado:", saida)
