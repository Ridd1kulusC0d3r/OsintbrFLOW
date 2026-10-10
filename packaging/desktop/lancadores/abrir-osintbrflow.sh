#!/bin/sh
# Abre o OSINT Brasil Flow (Linux). Deixe o terminal aberto enquanto usa o
# painel; fechá-lo (ou Ctrl+C) encerra o laboratório.
cd "$(dirname "$0")" || exit 1
if [ ! -x "OsintbrFLOW/OsintbrFLOW" ]; then
  echo "Não encontrei o aplicativo. Este arquivo precisa ficar ao lado da pasta OsintbrFLOW."
  exit 1
fi
exec "./OsintbrFLOW/OsintbrFLOW" "$@"
