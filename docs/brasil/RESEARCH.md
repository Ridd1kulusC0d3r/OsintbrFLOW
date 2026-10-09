# Pesquisa de referência e decisões de produto

Inspeção realizada em 9 de outubro de 2026. Leitura direcionada do código de arquitetura, ingestão, representação, execução e catálogo; não é uma auditoria exaustiva de todas as linhas ou dependências.

## Fontes fixadas

| Fonte | Snapshot consultado | Arquivos / superfície examinados |
|---|---|---|
| [Flowsint](https://github.com/reconurge/flowsint) | `4c05849bc6ca5055ad187d056ef26e61b3bc2fea` | README, NOTICE, LICENSE, pyprojects, Dockerfiles, Compose, registries, Enricher, orchestrator, tasks/flow, schemas, importação JSON, tipos Organization/Phone, rotas, navegação, Vite |
| [SpiderFoot](https://github.com/smicallef/spiderfoot) | `0f815a203afebf05c98b605dba5cf0475a0ee5fd` | README, LICENSE, sfscan.py e spiderfoot/plugin.py, notifyListeners, eventos e prevenção de ciclos |
| [OSINT Brazuca](https://github.com/osintbrazuca/osint-brazuca) | `c5596fd157bdbfecad8a9571245556cd3348b3df` | README, LICENSE, data/sources.json, taxonomia e estrutura de geração |
| [OSIRIS](https://github.com/simplifaisoul/osiris) | `4de829041ec187f5acdb053f387c993a594e703f` | README, LICENSE, estrutura Next/API, src/lib/sourceCache.ts e catálogo de rotas OSINT |
| [OSINT Brasil](https://osint.juanmathewsrebellosantos.com/) | Consulta pública em 2026-10-09 | HTML e módulos frontend servidos publicamente: App.jsx e AppContext.jsx; filtros, favoritos, estados e categorias |

## Flowsint é a base, não só inspiração visual

O monorepo separa tipos Pydantic, enriquecedores registrados por decorator, core, API FastAPI e frontend React. Celery executa enrichers/flows; Neo4j armazena o grafo; PostgreSQL suporta os dados da aplicação. O orchestrator mantém registros de execução JSON e o frontend tem editor de fluxos. O enrich de Organization examinado usa SIRENE, com modelo de propriedades francesas.

Decisão: preservar o código, seus créditos e licença, acrescentar tipos BR em vez de encaixar CNPJ em campos SIREN. Também corrigimos a importação tipada: o parser reconstruía entidades pelo label e perdia `nodeProperties`, comportamento inadequado para transferir evidências.

A licença atual consultada é Apache-2.0. O NOTICE relata o histórico de relicenciamento; o arquivo foi preservado. O import é um snapshot identificado, não uma alegação de autoria do código original nem preservação do histórico Git completo.

## SpiderFoot: a contribuição arquitetural

`notifyListeners` relaciona eventos com seus antecessores e evita propagar ciclos encontrados na ancestralidade; os módulos declaram eventos consumidos e produzidos. Isso orientou o princípio de propagação limitada e rastreável. Nesta alpha, o motor brasileiro aceita apenas percursos tipados de até três etapas; não reutiliza nem executa os módulos SpiderFoot. Importador de eventos SpiderFoot e fila durável são evolução futura.

## OSINT Brazuca: fonte não é conector

O dataset contém categorias, entradas e links; as classificações são frequentemente heurísticas. Na amostra, uma referência de CNPJ aparecia com `input: cpf`: tratá-la automaticamente como contrato de API seria incorreto.

Adotamos nomes, descrições e URLs com atribuição MIT. Filtramos HTTPS e deduplicamos por URL exata, produzindo 1.168 referências. Não inferimos capacidade de automação a partir da categoria. As três APIs implementadas são adicionadas separadamente. Não foi feita verificação individual de disponibilidade desses 1.168 links.

## OSIRIS: separar apresentação e confiabilidade

A estrutura consultada agrega camadas de contexto e rotas de dados. `sourceCache.ts` implementa TTL, deduplicação de chamadas em andamento e fallback para dados anteriores quando a fonte falha. Isso é útil para mapas de situação, mas exige cuidado em evidência temporal: um fallback não deve parecer uma nova observação.

Escolha nesta versão: não servir coletas antigas como novas. Falhas são explícitas, baseline só compara execuções completas e datas permanecem visíveis. Não copiamos scanners, previsões por agentes ou fontes de câmeras; não avaliamos as alegações de escala/desempenho do README do OSIRIS.

## Portal OSINT Brasil

A interface pública apresenta múltiplas formas de descoberta, contagem de ferramentas, busca, categorias, favoritos e estados de disponibilidade. Os módulos consultados usam estado React e armazenamento local para preferências. Essas são boas referências de navegação. O número anunciado pelo portal não foi auditado. Não houve redistribuição do seu catálogo ou código sem confirmação de licença.

## Comparação de escopo: sem ranking fabricado

| Critério | Flowsint consultado | OsintbrFLOW 0.1.0 |
|---|---|---|
| Grafos e editor genérico | Base existente | Preservados |
| Empresa brasileira tipada e DV alfanumérico | Não localizados no recorte examinado | Implementados |
| CNPJ → CEP → município | Não localizado no recorte examinado | Implementado e executado com APIs reais |
| Referências BR versus conectores | Não localizado no recorte examinado | Distinção explícita no atlas |
| Comparação de snapshots BR | Não localizada no recorte examinado | Campo a campo, com baseline e falhas distintas |
| Pacote BR verificável | Não localizado no recorte examinado | Hashes, cadeia e verificador offline |
| Escala/multiusuário em produção | Não auditado | Não validado |

Ausência no recorte não prova ausência em todo o projeto. Não se usaram estrelas ou marketing como evidência de superioridade técnica.

## Referências dos contratos implementados

- [BrasilAPI — documentação CNPJ](https://brasilapi.com.br/docs): intermediário da consulta; não se apresenta como certidão oficial.
- [ViaCEP — documentação e exemplos](https://viacep.com.br/): CEP e código IBGE.
- [IBGE — API Localidades](https://servicodados.ibge.gov.br/api/docs/localidades): identificação municipal.
- [Receita Federal — manual do DV alfanumérico](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf): caracteres ASCII menos 48, pesos e módulo 11. Exemplo `12.ABC.345/01DE-35` coberto por teste.

Aceitar um CNPJ alfanumérico no validador não garante que todo provedor já possua aquele registro.
