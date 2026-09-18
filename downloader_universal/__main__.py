"""Linha de comando do Downloader Universal.

Uso local (fora do Colab)::

    python -m downloader_universal URL [URL...] [--pasta downloads]
"""

from __future__ import annotations

import argparse

from .config import CONFIG
from .engine import baixar_varios


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="downloader_universal",
        description="Baixa arquivos de MediaFire, Google Drive, RapidGator, "
                    "Sharemods, DDownload, MEGA, OneDrive, links diretos e mais.",
    )
    parser.add_argument("urls", nargs="+", help="URLs para baixar")
    parser.add_argument("--pasta", default=None,
                        help="pasta de destino (padrão: "
                             f"{CONFIG['pasta_downloads']})")
    parser.add_argument("--force", action="store_true",
                        help="baixa de novo mesmo se o arquivo já existe")
    args = parser.parse_args(argv)

    resultados = baixar_varios(args.urls, pasta=args.pasta, force=args.force)
    if not all(r["ok"] for r in resultados):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
