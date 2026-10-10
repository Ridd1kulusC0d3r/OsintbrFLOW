#!/bin/sh
# Abre o OSINT Brasil Flow (macOS). Deixe a janela do Terminal aberta
# enquanto usa o painel; fechá-la encerra o laboratório.
cd "$(dirname "$0")" || exit 1
if [ ! -x "OsintbrFLOW/OsintbrFLOW" ]; then
  echo "Não encontrei o aplicativo. Este arquivo precisa ficar ao lado da pasta OsintbrFLOW."
  read -r _
  exit 1
fi
# Arquivos baixados recebem a marca de quarentena; sem removê-la da pasta
# do aplicativo, o macOS bloqueia cada biblioteca interna separadamente.
xattr -dr com.apple.quarantine OsintbrFLOW 2>/dev/null
exec "./OsintbrFLOW/OsintbrFLOW" "$@"
