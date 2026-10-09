# Validação da entrega 0.1.0

Data: 2026-10-09. Ambiente: Python 3.12, Node 24, Chromium headless.

| Verificação | Resultado |
|---|---|
| Testes Python da camada brasileira | 29 passaram |
| Integração de três enriquecedores + importador JSON herdado | 1 passou; graph service simulado, sem servidor Neo4j |
| CNPJ de exemplo numérico e alfanumérico da Receita | Passou; DVs incorretos, repetição de dígitos e entradas malformadas rejeitados |
| Consultas reais individuais | BrasilAPI CNPJ, ViaCEP e IBGE responderam e passaram validação de identidade |
| Percurso real completo | CNPJ público `00000000000191` → CEP retornado → município IBGE: completo, três evidências |
| Resposta HTTP 404/429/5xx, redirect, JSON inválido, payload grande, identidade divergente | Contratos testados com MockTransport |
| Hash de resposta, adulteração, ordem da cadeia, reinício do Store | Passou |
| Oito appends concorrentes | Cadeia íntegra |
| API: usuário A tentando ler/executar caso de B | 404, sem coleta |
| Coleta parcial versus baseline | Não produz diferença de remoção |
| `npm run typecheck:brasil` | Passou |
| `npm run build` | Passou; warning de chunks grandes herdados |
| Navegador desktop 1440 px | Laboratório, grafo, repetição, diff, evidências e catálogo: passou; zero pageerrors |
| Navegador móvel 390 px | Sem overflow horizontal; layout inspecionado e grafo adaptado à orientação vertical |
| Recarga da página | Caso e histórico recuperados do backend |
| Stack Docker completo | Não executado: Docker indisponível neste ambiente |
| `typecheck` global | 88 erros em código herdado; os mesmos 88 também reproduzidos no snapshot upstream com as mesmas dependências |
| Desempenho em escala e isolamento multiusuário completo do upstream | Não auditados |

Os testes de API usam injeção de identidade para verificar o isolamento do Store/router. A autenticação JWT do Flowsint não foi reimplementada e não foi submetida a uma auditoria completa nesta entrega. Os testes não equivalem a homologação de produção.

## Problemas herdados identificados

O typecheck global aponta, entre outros, referências a pacotes Tiptap ausentes/incompatíveis, propriedades antigas de GraphNode e inconsistências de tipos. Esses problemas não devem ser escondidos por `skip` global ou casts indiscriminados. A CI Brasil executa sua checagem específica e a compilação completa. Um gate de typecheck completo fica pendente no roadmap.

A configuração Vite espalhava o resultado do plugin TanStack em um objeto; a geração da nova rota não ocorreu na primeira compilação. Foi corrigida para usar o plugin diretamente, e `tsr generate` passou a fazer parte de build/dev. A rota `/dashboard/brasil` consta na árvore gerada.

Não foram executadas requisições de automação aos 1.168 links de referência. Eles são rotulados como pesquisa manual e não testados individualmente.

## Reproduzir

```bash
pip install -r requirements-brasil.txt pytest pytest-asyncio
PYTHONPATH=flowsint-types/src:flowsint-core/src pytest tests/brasil/test_brasil.py -q
npm ci --ignore-scripts --legacy-peer-deps
npm run typecheck:brasil --workspace flowsint-app
npm run build --workspace flowsint-app
```

Para testes nativos, instale também as dependências do core, acrescente `flowsint-enrichers/src` ao PYTHONPATH e execute `tests/brasil/test_native.py`. O teste não abre conexão Neo4j; ele verifica os objetos enviados ao serviço de grafo e a reimportação das entidades e arestas.
