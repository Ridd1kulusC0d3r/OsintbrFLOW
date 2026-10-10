#!/bin/sh
# Para quem instalou o pacote Python (wheel) com pipx
# Deixe o terminal aberto enquanto usa o painel; fechá-lo encerra o laboratório.
PATH="$HOME/.local/bin:$PATH"
if ! command -v osintbr >/dev/null 2>&1; then
  echo "Comando osintbr não encontrado. Instale o arquivo .whl da página de Releases com: pipx install ./osintbrflow-*.whl"
  echo "Depois rode: pipx ensurepath  e abra este arquivo de novo."
  read -r _
  exit 1
fi
exec osintbr "$@"
