# OSINT Brasil Flow

Laboratório de investigação empresarial e territorial: CNPJ → CEP → município, com casos, grafo, evidências com SHA-256 e pacote verificável. Roda só no seu computador.

```bash
pipx install osintbrflow
osintbr
```

O comando abre o painel no navegador. Os casos ficam na pasta de dados do usuário (`osintbr --print-data-dir`). O laboratório escuta apenas em `127.0.0.1` e não tem login: não o exponha à internet.

CPF e outros identificadores de pessoa física são recusados antes de qualquer chamada externa.

Código, documentação e limitações: https://github.com/Ridd1kulusC0d3r/OsintbrFLOW
