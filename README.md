# 📥 Downloader Universal

Baixa arquivos dos sites de hospedagem mais comuns da internet — direto no
**Google Colab** — e depois move tudo para o seu **Google Drive** ou para o
**seu computador**.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Viniciaao/Downloader-Universal/blob/main/Downloader_Universal.ipynb)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ O que ele faz

- ⬇️ Baixa arquivos de vários sites de hospedagem com um único comando: `baixar(url)`
- ☁️ Move os arquivos para uma pasta do seu **Google Drive**
- 💻 Ou envia direto para o **seu notebook/PC** (download pelo navegador)
- ↩️ **Retomada automática**: se a conexão cair, continua de onde parou
- 🔁 **Retentativas** automáticas em caso de instabilidade
- 📁 Suporta **pastas** do MediaFire e do Google Drive
- 🧠 Detecta o site sozinho — e tem um modo genérico para sites desconhecidos

## 🌐 Sites suportados

| Site | Status | Observações |
|---|---|---|
| **MediaFire** | ✅ | Arquivos e pastas, sem precisar de conta |
| **Google Drive** | ✅ | Arquivos e pastas compartilhados como "Qualquer pessoa com o link" |
| **Sharemods** | ✅ | Download grátis, espera automática do contador |
| **DDownload** | ✅ | Mesmo motor do Sharemods (XFileSharing) |
| **RapidGator** | 🔶 | Requer **conta premium** (o modo grátis usa captcha e bloqueia automação) |
| **MEGA** | ✅* | Instale o suporte opcional: `pip install mega.py` |
| **OneDrive / 1drv.ms** | ✅ | Links públicos de compartilhamento |
| **Centenas de sites XFS** | ✅ | UsersDrive, UploadRar, FileFox, HexUpload... detectados automaticamente |
| **Links diretos** | ✅ | Qualquer URL terminando em `.rar`, `.zip`, `.7z`, `.iso`, `.mp4`, ... |
| **Outros sites** | 🔶 | Análise da página + [yt-dlp](https://github.com/yt-dlp/yt-dlp) como último recurso |

> **XFS (XFileSharing)** é o script usado por centenas de sites de hospedagem.
> Se a página tiver os formulários típicos (`op=download1`/`download2`), o
> motor genérico resolve sozinho — mesmo sem o site estar na lista.

## 🚀 Como usar no Google Colab

1. Clique no selo **Open In Colab** lá em cima (ou abra
   [`Downloader_Universal.ipynb`](Downloader_Universal.ipynb)).
2. Rode as células em ordem (**Runtime ▸ Run all**).
3. Na célula de download, cole o link e execute:

```python
arquivo = baixar("https://www.mediafire.com/file/XXXX/arquivo.rar/file")
```

4. Mova para o Google Drive ou baixe para o seu computador:

```python
mover_para_drive(arquivo, pasta_drive="Meus Downloads")   # para o Drive
baixar_para_pc(arquivo)                                   # para o seu notebook
```

### Vários links de uma vez

```python
resultados = baixar_varios("""
https://www.mediafire.com/file/xxxx/jogo.rar/file
https://sharemods.com/abcdef/mod.zip.html
https://ddownload.com/123456789/outro.rar
https://drive.google.com/file/d/abc123/view
""")
```

### RapidGator (premium)

```python
configurar(rapidgator_usuario="seu@email.com", rapidgator_senha="sua_senha")
baixar("https://rapidgator.net/file/ABC123/arquivo.rar.html")
```

## 💻 Usando fora do Colab (no seu PC)

```bash
git clone https://github.com/Viniciaao/Downloader-Universal.git
cd Downloader-Universal
pip install -r requirements.txt

python -m downloader_universal "https://www.mediafire.com/file/XXXX/arquivo.rar/file" --pasta downloads
```

Os arquivos já caem direto no seu computador. Também dá para importar como
biblioteca:

```python
from downloader_universal import baixar
baixar("https://sharemods.com/abcdef/mod.zip.html", pasta="meus_arquivos")
```

## 📚 API rápida

| Função | O que faz |
|---|---|
| `baixar(url, pasta=None, force=False)` | Baixa um arquivo/pasta e retorna o caminho |
| `baixar_varios(urls, pasta=None)` | Baixa uma lista de links sem parar nos erros |
| `configurar(**opcoes)` | Muda pasta padrão, credenciais do RapidGator, etc. |
| `montar_drive()` | Monta o Google Drive no Colab |
| `mover_para_drive(item, pasta_drive="Downloader Universal")` | Move para o Drive |
| `copiar_para_drive(item, pasta_drive=...)` | Copia (mantém no Colab) |
| `mover_tudo_para_drive(pasta=None, pasta_drive=...)` | Move a pasta de downloads inteira |
| `baixar_para_pc(caminho)` | Envia o arquivo para o seu computador |
| `zipar(caminho)` | Compacta em `.zip` (bom para arquivos grandes) |

## 🩺 Solução de problemas

| Problema | Solução |
|---|---|
| `RapidGator bloqueia download automático` | É necessário conta **premium** + `configurar(rapidgator_usuario=..., rapidgator_senha=...)` |
| Google Drive: `Access denied` | O dono do arquivo precisa compartilhar como "Qualquer pessoa com o link" |
| `Não consegui extrair o link direto` | O arquivo pode ter sido removido ou o site mudou — abra uma [issue](../../issues) com o link |
| MEGA: módulo não instalado | `pip install mega.py` |
| Download lento no Colab | Normal: depende do servidor de origem e da cota da sua conta |
| Sessão do Colab expirou | Os arquivos em `/content` são apagados; sempre mova para o Drive |

## ⚖️ Aviso legal

Esta ferramenta é para uso com arquivos que **você tem direito de baixar**
(seus próprios arquivos, conteúdo livre/autorizado, etc.). Respeite os termos
de uso dos sites e as leis de direitos autorais do seu país. O uso indevido é
responsabilidade do usuário.

## 🔧 Testes

```bash
python tests/test_parsers.py   # testes offline dos parsers (sem rede)
```

## 📄 Licença

[MIT](LICENSE) — use, modifique e compartilhe à vontade.
