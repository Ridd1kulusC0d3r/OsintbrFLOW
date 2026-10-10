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


## Opção Google Colab

Notebook: `notebooks/OsintbrFLOW_Colab.ipynb`. Acrescenta instalação isolada, Node 24 com checksum, build dedicado e interface incorporada pelo proxy oficial do Colab. O laboratório exige um token por sessão quando o proxy está configurado; o modo local continua restrito a localhost.

Validação desta alteração (2026-10-09):

- 41 testes Python passaram (29 existentes + 12 de configuração, controle de acesso e notebook).
- Instalação limpa com `npm ci --ignore-scripts --legacy-peer-deps`, typecheck Brasil e build dedicado passaram.
- Chromium local: token enviado pela interface, caso demonstrativo com três entidades, remoção do token da URL e recarga autenticada; zero erros de página.
- Células Python do notebook analisadas sintaticamente; sem resultados ou credenciais salvos.
- A sessão hospedada no Google Colab **não foi executada neste ambiente**. Autenticação Google, disponibilidade da VM e integração com o proxy real ainda dependem do primeiro teste no Colab. A checagem local não equivale a essa validação.

Para repetir os testes adicionais:

```bash
PYTHONPATH=flowsint-types/src:flowsint-core/src pytest tests/brasil/test_brasil.py tests/brasil/test_colab.py -q
npm run build:brasil --workspace flowsint-app
```


### Correção do proxy Colab — Host não autorizado

O primeiro teste do usuário no Colab retornou `403 Host não autorizado`, falha que a validação local anterior não cobria. A captura não inclui o valor do cabeçalho recebido; portanto, não é possível atribuir o erro a um hostname específico.

A correção separa os dois modos: localhost mantém sua lista restrita de hosts; Colab exige a chave Bearer em todas as rotas `/api/` e valida a origem quando presente, sem usar o Host encaminhado pelo proxy como credencial. O HTML e os assets não contêm casos nem chaves. O notebook usa `proxyPort(..., {cache: false})` e passa uma URL absoluta ao iframe, preservando a mesma origem configurada no servidor.

Foram acrescentadas seis variações de Host aos testes: hosts locais, IPv6, host interno, domínio alternativo e host arbitrário. Em todos, o painel está acessível, os dados sem chave são recusados, a chave correta permite a consulta e origens externas continuam bloqueadas. A confirmação em uma sessão real do Colab após esta correção ainda está pendente.


## Revisão do Colab, autoteste e recusa de CPF — 2026-10-09

**Ambiente:** sandbox Linux x86_64, Python 3.13, Node 22/npm 10 e npm 11.21. A rede de saída deste ambiente bloqueia `nodejs.org`, BrasilAPI, ViaCEP e IBGE; por isso o Node 24 foi substituído pelo Node local e as fontes reais não puderam ser alcançadas daqui. A sessão hospedada no Google Colab continua **não executada** por esta revisão.

**Método:** as células reais do notebook foram executadas em sequência, sem edição, com um substituto local de `google.colab.output` (`proxyPort` e `serve_kernel_port_as_iframe`) e `/content` criado na máquina. Só o trecho de download do Node foi trocado.

| Verificação | Resultado |
|---|---|
| Células 1–3 em ambiente limpo | Passaram; servidor em modo `colab-proxy`, painel servido com Host reescrito |
| API sem chave / Origin externa / chave correta | 401 / 403 / 200 |
| Caso demonstrativo pela API autenticada | Três evidências `ok` |
| Coleta real sem acesso à rede | `failed` com `unavailable` registrado; nenhuma conclusão de inexistência |
| **Segunda “Executar tudo” na mesma sessão (notebook anterior)** | **Falhava**: `npm ci` (npm 10 e 11) reescreve `yarn.lock`, e a célula 1 abortava com “Há alterações locais no código” |
| Segunda “Executar tudo” após a correção | Passou duas vezes seguidas; checkout limpo ao final |
| Entrada com formato de CPF nos três tipos e nos dois modos | 422 com mensagem explícita; zero requisições externas; valor não ecoado nem gravado |
| Célula 4 (autoteste) | 59 testes passaram; fontes marcadas ⚠️ (bloqueio de rede deste ambiente); recusa de CPF ✅ |
| Suíte `test_brasil.py` + `test_colab.py` | 59 passaram (47 anteriores + 12 de recusa de CPF) |

**Pendente:** executar a célula 4 numa sessão real do Colab e anexar `/content/osintbrflow-autoteste.json` a esta seção. É a primeira evidência de ponta a ponta com proxy Google, Node 24 e as três fontes reais.

**Observação:** `starlette.testclient` emite aviso de depreciação do `httpx`. Não afeta o laboratório, mas o limite `httpx<0.29` em `requirements-brasil.txt` deve ser revisto antes que o aviso vire erro.


## Aplicativo de desktop (Degrau 2) — 2026-10-09

**O que mudou:** o comando `osintbr` ganhou `--janela` (janela própria com pywebview, extra opcional `osintbrflow[janela]`) e `--navegador`; dentro do executável, a janela própria é o padrão. Sem pywebview, ou sem suporte gráfico no sistema, o painel abre no navegador com uma linha de aviso. Fechar a janela encerra o servidor. Continua sem opção de escutar fora de `127.0.0.1`; `lab.py` não foi alterado.

**Construído e executado aqui (Linux):** sandbox x86_64, Python 3.12.3, PyInstaller 6.22.3, painel `dist-brasil` já compilado. Comando: `python packaging/desktop/build.py --zip`.

| Item | Resultado |
|---|---|
| Formato | Uma pasta (onedir): abre direto, sem descompactar a cada partida como o onefile |
| Tempo de build | ~33 s |
| Pasta do aplicativo | 40,4 MB (sem pywebview); 40,9 MB com pywebview |
| Zip de distribuição (aplicativo + COMECE-AQUI.md + lançadores) | 22,1 MB |
| Partida a frio até `/health` (cache de disco limpo) | 0,69 s; partidas seguintes 0,63–0,65 s |
| Conteúdo proibido no pacote (`.env`, `node_modules`, `tests`, banco, venv) | Nenhum (verificado pelo build) |

`python packaging/desktop/smoke_test.py <executável>` (só biblioteca padrão, sem tela) passou no executável, no lançador `abrir-osintbrflow.sh` extraído do zip e no comando `osintbr` instalado a partir do wheel:

| Verificação | Resultado |
|---|---|
| `/health` | 200, modo `local-only` |
| Caso criado com `Origin: http://127.0.0.1:<porta>` / Origin diferente | 201 / 403 |
| Rota demonstrativa CNPJ `11222333000181` → CEP → município | 3 evidências `ok` |
| Semente com formato de CPF (sintético `52998224725`) | 422 |
| Exportação | 1 coleta |
| Banco em `OSINTBR_HOME/brasil.sqlite3` | Sim |
| Encerramento por Ctrl+C | Código 0, sem traceback |

Com pywebview 6.2.1 instalado e sem GTK/Qt (caso deste sandbox), `osintbr --janela` e o executável com pywebview empacotado caíram para o navegador com uma linha de aviso, e o Ctrl+C encerrou limpo.

**Suíte:** `tests/brasil` → 80 passaram, 1 ignorado (`test_native.py`, depende do núcleo Flowsint completo). Os 9 testes novos de janela usam um módulo `webview` simulado e não precisam de tela.

**Só o CI vai verificar (`.github/workflows/release.yml`):** build e teste de fumaça no Windows (x64) e no macOS (arm64), ícone `.ico` do Windows (gerado com Pillow), lançadores `.bat` e `.command`, e o fluxo de Release com `SHA256SUMS.txt`. Nada disso foi executado aqui.

**Não verificado em lugar nenhum ainda:** a janela própria aparecendo de fato (WebView2 no Windows, WebKit no macOS); os avisos SmartScreen/Gatekeeper descritos no `COMECE-AQUI.md`; o duplo clique nos lançadores em cada sistema. O macOS não ganhou `.icns` nem pacote `.app`: o executável roda pelo lançador `.command`. Os aplicativos não são assinados.


## Degrau 3 — hospedagem para equipe — 2026-10-09

**Escopo:** `compose.prod.yml`, `deploy/Caddyfile`, `scripts/init-prod.py`, chave `FLOWSINT_ALLOW_REGISTRATION` na API, recusa de IPs públicos no laboratório e o guia `docs/brasil/DEPLOY.md`.

**Ambiente:** sandbox Linux x86_64, Python 3.13, Docker Compose v5.5.1 **sem daemon Docker**, Caddy v2.11.4 (binário oficial distribuído no pacote PyPI `caddy-bin`). Sem DNS público, sem portas 80/443 alcançáveis, sem Let's Encrypt.

> **Uma implantação real não foi executada.** Nenhuma imagem foi compilada, nenhum container subiu, nenhum certificado foi emitido, e os comandos de backup e restauração do DEPLOY.md não foram rodados. O primeiro deploy numa VPS é o primeiro teste de ponta a ponta.

| Verificação | Resultado |
|---|---|
| `docker compose --env-file <gerado> -f compose.br.yml -f compose.prod.yml config` | Passou. Só `caddy` publica portas (80, 443, 443/udp); `postgres`, `redis`, `neo4j`, `api`, `app` sem portas; todos com `restart: unless-stopped`, limite de memória, rotação de log 10 MB × 5 e healthcheck; `ALLOWED_ORIGINS=https://<domínio>` e `FLOWSINT_ALLOW_REGISTRATION=false` na API |
| Mesmo comando sem `DOMAIN` | Falha com “required variable DOMAIN is missing” (esperado) |
| `caddy validate` e `caddy fmt` | “Valid configuration”; arquivo formatado |
| Caddy rodando localmente em HTTP contra um servidor simulado no lugar do nginx | HSTS, `nosniff`, `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `Referrer-Policy`, `Permissions-Policy` presentes; `X-Frame-Options` do upstream substituído (não duplicado); `Server` removido; Host repassado como `localhost`; corpo de 11 MB → **413**, corpo pequeno → 200 |
| Testes da API (`flowsint-api/tests`) | **32 passaram** (17 existentes + 15 novos da chave de cadastro) |
| Testes `tests/brasil` | **86 passaram, 1 ignorado** (59 anteriores + 11 de recusa de IP público no laboratório + 16 do `init-prod.py` e contratos estáticos de deploy) |

Novos testes da chave de cadastro cobrem: ausente = aberto (comportamento do upstream preservado); `true/1/yes/on` abre; `false`, vazio e erros de digitação fecham com 403 sem criar conta; login continua funcionando com o cadastro fechado.

Não verificado aqui: emissão real do certificado, redirecionamento HTTP→HTTPS, HTTP/3, healthchecks com `wget` dentro das imagens `nginx:1.29-alpine` e `caddy:2.11-alpine`, consumo real de memória, SSE pelo Caddy + nginx com o app real, `pg_dump`/`neo4j-admin dump`/`load` e as permissões de volume do Neo4j, e o comportamento do laboratório recebendo tráfego pelo NAT do Docker (o teste simula o endereço do cliente).

Para repetir:

```bash
PYTHONPATH=flowsint-types/src:flowsint-core/src python -m pytest tests/brasil -q
# Ambiente com as dependências da API (as dos repositórios git do upstream não são necessárias para estes testes):
cd flowsint-api && REDIS_URL=redis://localhost:6379/0 python -m pytest -q
python3 scripts/init-prod.py --domain osint.exemplo.com.br --email ti@exemplo.com.br --path /tmp/env.prod
docker compose --env-file /tmp/env.prod -f compose.br.yml -f compose.prod.yml config -q
DOMAIN=osint.exemplo.com.br ACME_EMAIL=ti@exemplo.com.br caddy validate --config deploy/Caddyfile --adapter caddyfile
```

**Observações sobre o upstream encontradas nesta revisão:**

- Cadastro público aberto por padrão e sem limitação de tentativas no login; nenhuma política de senha.
- `.env.example` traz `AUTH_SECRET=superscretchangeitplz`, uma `MASTER_VAULT_KEY_V1` fixa e `NEO4J_PASSWORD=password`; quem copia sem trocar tem sessões forjáveis. `init-prod.py` recusa esses valores.
- Token de sessão válido por 60 horas (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 60`), sem revogação.
- O campo `is_active` de `profiles` não é verificado no login nem em `get_current_user`.
- `/api/auth/users/search` permite a qualquer conta listar e-mails de outras contas por prefixo (pensado para compartilhamento; relevante quando a equipe não deve se conhecer).
- CORS do upstream usa lista explícita (`ALLOWED_ORIGINS`) com `allow_credentials=True`, sem `*`: adequado.
