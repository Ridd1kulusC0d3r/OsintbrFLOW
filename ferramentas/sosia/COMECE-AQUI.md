# COMECE AQUI — SÓSIA

Gera nomes **quase iguais** ao de uma marca ou pessoa (`banc0aurora`, `bancoaurora_suporte`, `banc0aurora_oficial`…), verifica em quais plataformas eles **já estão registrados**, lê o nome de exibição e a bio de cada um para marcar como **CRÍTICO** quem imita o original de fato, **liga os perfis que publicam o mesmo WhatsApp, PIX ou link**, guarda as páginas como evidência, prepara a **denúncia** e mostra o que é **NOVO** ou **SUMIU** desde a última busca. Uso defensivo: proteção de marca e de pessoas expostas contra perfis imitadores usados em golpes.

## Em 3 passos

1. **Tenha o Python 3.9 ou mais novo.** Não sabe? Abra o `MANUAL.html` (dois cliques) e veja a seção *Instalação*.
2. **Dois cliques no lançador do seu sistema:**
   - Windows: `Iniciar-SOSIA.bat`
   - macOS: `Iniciar-SOSIA.command` (na 1ª vez: botão direito → Abrir → Abrir)
   - Linux: `iniciar-sosia.sh`
3. **Digite `DEMO`** e aperte Enter. O relatório abre sozinho no navegador.

O caso demo funciona **sem internet** (marca fictícia `bancoaurora`: 7 sósias em 4 plataformas, 3 CRÍTICOS, o mesmo WhatsApp ligando um perfil do Instagram a um do Telegram, 3 novos e 1 sumido desde uma busca anterior simulada, e uma plataforma descartada por mentir (soft-404)). Depois, rode de novo com um nome real. Tempo típico: 3 a 5 minutos (60 variantes × 12 plataformas + leitura dos perfis encontrados).

## O que tem nesta pasta

| Arquivo | Para que serve |
|---|---|
| `MANUAL.html` | Manual ilustrado completo (instalação por sistema, telas anotadas, problemas, glossário) |
| `GUIA-INTERATIVO.html` | O caso Banco Aurora: aprenda a ferramenta em 6 capítulos interativos, com fluxos e diagramas de uso |
| `sosia.py` | A ferramenta (um arquivo só) |
| `sites_padrao.json` | 12 plataformas, no formato do `data.json` do Sherlock |
| `Iniciar-SOSIA.bat` / `.command` / `iniciar-sosia.sh` | Lançadores de dois cliques |
| `demo/caso_demo.json` | Caso de demonstração fictício |
| `tests/` | Testes automáticos (`python -m unittest discover -s tests -v`) |
| `README.md` / `CHANGELOG.md` | Visão geral com imagens e diagramas / o que mudou em cada versão |
| `RELATORIO-DE-TESTES.md` | Resultado dos testes em nuvem, Python 3.9 a 3.14 |
| `resultados/` | Criada na primeira busca; uma subpasta por busca. **Mantenha-a**: é com ela que o SÓSIA compara a próxima busca |

## Depois da busca: o que abrir, nesta ordem

1. `relatorio.html`: comece pelos **CRÍTICOS**, depois os **NOVOS** e a seção **Pivôs**.
2. `denuncia.md`: o canal oficial de cada plataforma, os sinais e um texto pronto. Confirme o perfil antes de enviar.
3. `manifesto.txt`: anexe à denúncia. Os SHA-256 provam que as evidências em `evidencias/` não mudaram.

> **Novidades da 1.2:** pivôs de contato (`contatos.csv`), evidências com SHA-256 (`evidencias/`), kit de denúncia (`denuncia.md`) e exportação STIX 2.1 (`achados.stix.json`) para OpenCTI e MISP. Veja o `CHANGELOG.md`.

> **Atenção:** Nome parecido não é golpe, e CRÍTICO é indício forte, não prova. Abra cada perfil antes de concluir e use os canais oficiais de denúncia.
