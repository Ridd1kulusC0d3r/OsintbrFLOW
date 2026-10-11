#!/bin/bash
# SOSIA - lançador de dois cliques (macOS: .command | Linux: .sh)
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    python3 sosia.py "$@"
else
    echo
    echo "  Python 3 não encontrado."
    echo "  macOS: instale em https://www.python.org/downloads/"
    echo "  Linux: sudo apt install python3   (ou o gerenciador da sua distribuição)"
    echo
    command -v open >/dev/null 2>&1 && open "https://www.python.org/downloads/"
    read -r -p "Pressione Enter para sair."
fi
