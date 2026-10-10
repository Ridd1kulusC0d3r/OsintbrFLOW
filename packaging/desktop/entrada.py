"""Ponto de entrada do aplicativo de desktop (PyInstaller).

No executável, o painel abre em janela própria quando o pywebview foi
empacotado; caso contrário, no navegador. Sempre só em 127.0.0.1.
"""

import multiprocessing

from osintbr.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
