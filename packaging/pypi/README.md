# OSINT Brasil Flow

Laboratório de investigação empresarial e territorial: CNPJ → CEP → município, com casos, grafo, evidências com SHA-256 e pacote verificável. Roda só no seu computador.

```bash
# Enquanto o pacote não estiver no PyPI, instale o wheel baixado da página de Releases:
pipx install ./osintbrflow-0.2.0-py3-none-any.whl
osintbr
```

O comando abre o painel no navegador. Para usar uma janela própria, instale o extra `janela` (`pipx install './osintbrflow-0.2.0-py3-none-any.whl[janela]'`) e rode `osintbr --janela`; se o sistema não tiver suporte gráfico, o painel abre no navegador. Os casos ficam na pasta de dados do usuário (`osintbr --print-data-dir`). O laboratório escuta apenas em `127.0.0.1` e não tem login: não o exponha à internet.

CPF e outros identificadores de pessoa física são recusados antes de qualquer chamada externa.

Código, documentação e limitações: https://github.com/Ridd1kulusC0d3r/OsintbrFLOW
