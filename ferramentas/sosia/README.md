# SÓSIA 1.1

Gera nomes **quase iguais** ao de uma marca ou pessoa (`banc0aurora`, `bancoaurora_suporte`, `banc0aurora_oficial`…), verifica em quais plataformas eles **já estão registrados**, lê nome de exibição e bio para marcar os **CRÍTICOS** e compara com a busca anterior (**NOVO** / **SUMIU**). Uso defensivo: proteção de marca e de pessoas expostas contra perfis imitadores usados em golpes.

Sherlock e Maigret procuram o nome **exato**. Golpista usa o nome **quase** exato. O SÓSIA gera as variantes (homóglifos, iscas de "suporte/oficial", separadores, erros de digitação) e testa cada plataforma com um nome impossível antes de confiar nela.

```bash
python sosia.py --demo            # exemplo sem internet
python sosia.py NOME              # busca real
python sosia.py --help            # todas as opções
```

- Python 3.9+, **só biblioteca padrão** (nada de `pip install`)
- Lê o `data.json` do [Sherlock](https://github.com/sherlock-project/sherlock) sem modificação (`--sites data.json`)
- Saídas: `relatorio.html`, `achados.csv`, `mudancas.csv`, `variantes.txt`, JSON e `manifesto.txt` com SHA-256
- `--sem-perfil` para não abrir os perfis; monitoramento automático usando a mesma pasta `--saida`
- Comece por `COMECE-AQUI.md`; manual completo em `MANUAL.html`

Licença MIT. Lista de sites: subconjunto do Sherlock Project (MIT), ver `LICENSE-sherlock-data.txt`.
