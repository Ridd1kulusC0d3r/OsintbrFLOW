# Hospedar o OsintbrFLOW para uma equipe (Degrau 3)

> **Situação em 2026-10-09:** os arquivos deste guia foram verificados de forma estática (sintaxe, combinação dos arquivos Compose, configuração do Caddy, testes automatizados). **Nenhuma implantação real foi executada.** O primeiro deploy numa VPS é também o primeiro teste de ponta a ponta. Faça-o num servidor sem dados reais e siga a lista de conferência no fim. Detalhes em [VALIDATION.md](VALIDATION.md).

## Para quem é

Equipes pequenas (até cerca de 10 pessoas) que querem usar o **fork completo do Flowsint** com o painel Brasil a partir de um endereço `https://`, com login individual.

Não é para:

- **O laboratório Brasil** (`compose.lab.yml`, `Dockerfile.brasil`, `scripts/brasil.py`). Ele **não tem login** e **nunca deve ser exposto à internet**, nem atrás deste Caddy, nem atrás de outro proxy. Ver a seção [O laboratório não se hospeda](#o-laboratório-não-se-hospeda).
- Uso por muitas organizações, dados sob sigilo legal, ou ambientes que exigem certificação. Ver [O que não está feito](#o-que-não-está-feito).

## Como fica

```text
Internet ──443/80──▶ Caddy (HTTPS automático, cabeçalhos de segurança)
                       │  rede "edge"
                       ▼
                     app (nginx: interface + repasse /api)
                       │  rede interna
                       ▼
     API ── worker ── PostgreSQL ── Neo4j ── Redis ── volume brasil_data (SQLite)
```

Só o Caddy publica portas no servidor. Banco de dados, grafo, fila e API ficam acessíveis apenas dentro da rede interna do Docker.

Arquivos envolvidos:

| Arquivo | Papel |
|---|---|
| `compose.br.yml` | Os seis serviços do fork completo (já existia) |
| `compose.prod.yml` | Sobreposição de produção: Caddy, sem portas internas, limites, logs, reinício |
| `deploy/Caddyfile` | HTTPS, cabeçalhos de segurança, limite de tamanho de envio |
| `scripts/init-prod.py` | Gera e confere `.env.prod` com segredos fortes |

## Tamanho do servidor

Os limites de memória em `compose.prod.yml` somam cerca de 6 GB, mas nem todos são usados ao mesmo tempo.

| Serviço | Limite | Observação |
|---|---|---|
| Neo4j | 2 GB | heap 512 MB–1 GB + cache de páginas 512 MB |
| PostgreSQL | 1 GB | |
| API | 1 GB | |
| Worker (Celery) | 1,5 GB | 10 tarefas simultâneas |
| Redis | 256 MB | fila, sem dados permanentes |
| Caddy / frontend | 256 MB / 128 MB | |

- **Mínimo:** 4 GB de RAM, 2 vCPU, 40 GB de disco SSD, com 2 GB de swap.
- **Recomendado:** 8 GB de RAM, 4 vCPU, 80 GB de SSD.
- **A compilação** (`--build`) do frontend usa bastante memória. Em máquinas de 4 GB, crie o swap antes de compilar.

Esses números são estimativas a partir das configurações. Não foram medidos sob carga.

## Passo a passo numa VPS Linux

Pré-requisitos: Ubuntu 24.04 ou Debian 12 (ou equivalente), acesso `sudo`, um domínio seu, Docker Engine com o plugin `docker compose` **2.24 ou mais novo** (instale pelo [guia oficial](https://docs.docker.com/engine/install/)); versões antigas não entendem a marcação `!reset` usada para fechar as portas internas e falham ao combinar os arquivos.

### 1. DNS

No painel do seu domínio, crie um registro **A** (e **AAAA**, se a VPS tiver IPv6) apontando, por exemplo, `osint.suaorg.com.br` para o IP da VPS. Espere a propagação: `dig +short osint.suaorg.com.br` deve devolver o IP.

O HTTPS automático (Let's Encrypt) só funciona se o nome já apontar para a máquina e as portas 80 e 443 estiverem abertas.

### 2. Firewall

```bash
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
```

> **Atenção:** portas publicadas pelo Docker **ignoram o ufw**. Por isso `compose.prod.yml` publica só 80 e 443. Não acrescente `ports:` a nenhum outro serviço.

### 3. Código e segredos

```bash
git clone https://github.com/Ridd1kulusC0d3r/OsintbrFLOW.git
cd OsintbrFLOW
python3 scripts/init-prod.py --domain osint.suaorg.com.br --email ti@suaorg.com.br
```

O script:

- cria `.env.prod` com permissão 600 e segredos aleatórios (senhas do PostgreSQL e do Neo4j, chave de assinatura das sessões, chave do cofre de chaves de API);
- **não sobrescreve** um `.env.prod` existente; se ele existir, só o confere;
- **recusa** segredos vazios, curtos ou conhecidos (como os do `.env.example` do upstream);
- não exibe nenhum segredo na tela.

Guarde uma cópia de `.env.prod` no cofre de senhas da equipe. **Sem `MASTER_VAULT_KEY_V1`, as chaves de API salvas no sistema ficam ilegíveis**, mesmo com backup.

Para conferir depois: `python3 scripts/init-prod.py --check`.

### 4. Primeira subida e contas da equipe

O Flowsint **não tem papel de administrador**: toda conta tem os mesmos poderes, e cada pessoa vê só as próprias investigações e as que forem compartilhadas com ela. "Criar o administrador" significa, na prática, criar as contas da equipe e depois fechar o cadastro.

1. Edite `.env.prod` e troque `FLOWSINT_ALLOW_REGISTRATION=false` por `true`.
2. Suba tudo:

   ```bash
   docker compose --env-file .env.prod -f compose.br.yml -f compose.prod.yml up -d --build
   docker compose --env-file .env.prod -f compose.br.yml -f compose.prod.yml ps
   ```

   Todos os serviços devem aparecer como `healthy` em alguns minutos. O Neo4j é o mais lento.
3. Abra `https://osint.suaorg.com.br/register` e crie as contas. A API não impõe tamanho mínimo de senha: combinem senhas longas (12+ caracteres, gerenciador de senhas).
4. **Feche o cadastro:** volte `FLOWSINT_ALLOW_REGISTRATION=false` e aplique:

   ```bash
   docker compose --env-file .env.prod -f compose.br.yml -f compose.prod.yml up -d
   ```

5. Confirme que fechou: `curl -s -o /dev/null -w '%{http_code}\n' -X POST https://osint.suaorg.com.br/api/auth/register -H 'Content-Type: application/json' -d '{"email":"teste@exemplo.com","password":"x"}'` deve mostrar **403**.

Para incluir alguém depois, repita os passos 1, 4 e 5. Com o cadastro fechado, a tela `/register` continua aparecendo, mas o envio é recusado com a mensagem "Cadastro público desativado neste servidor".

> Se `FLOWSINT_ALLOW_REGISTRATION` estiver ausente, `compose.prod.yml` assume `false`. Qualquer valor que não seja `true`, `1`, `yes` ou `on` também fecha o cadastro: um erro de digitação deixa o sistema fechado, não aberto.

Dica: para não repetir o comando longo, crie um atalho na sessão:

```bash
alias osint='docker compose --env-file .env.prod -f compose.br.yml -f compose.prod.yml'
osint ps
```

Os exemplos abaixo usam esse atalho.

## Backups

Há **três** lugares com dados, e cada um precisa do próprio backup:

| Dado | Onde | Como |
|---|---|---|
| Contas, investigações, sketches, chaves de API (cifradas) | PostgreSQL | `pg_dump` |
| Grafos dos sketches | Neo4j | `neo4j-admin database dump` (com o Neo4j parado) |
| Casos e evidências do painel Brasil | SQLite no volume `brasil_data` | cópia com a API do SQLite |
| Segredos | `.env.prod` | cofre de senhas, fora do servidor |

```bash
mkdir -p backup && chmod 700 backup
DATA=$(date +%F)

# 1. PostgreSQL (sem parar o sistema)
osint exec -T postgres pg_dump -U flowsint -Fc flowsint > backup/pg-$DATA.dump

# 2. Painel Brasil (cópia consistente mesmo com o sistema no ar)
osint exec -T api python -c "import sqlite3; s=sqlite3.connect('/home/flowsint/brasil-data/brasil.sqlite3'); d=sqlite3.connect('/tmp/brasil-backup.sqlite3'); s.backup(d); d.close()"
osint cp api:/tmp/brasil-backup.sqlite3 backup/brasil-$DATA.sqlite3

# 3. Neo4j (exige parar o Neo4j por alguns minutos na edição Community)
osint stop celery api neo4j
docker run --rm -v osintbrflow_neo4j_data_prod:/data -v "$PWD/backup":/backups \
  --user "$(id -u):$(id -g)" neo4j:5 neo4j-admin database dump neo4j --to-path=/backups
mv backup/neo4j.dump backup/neo4j-$DATA.dump
osint up -d
```

Depois, **copie a pasta `backup/` para fora da VPS** (outro provedor, armazenamento de objetos com criptografia, disco da organização). Um backup que fica só no mesmo servidor não protege contra perda do servidor.

Os backups contêm os mesmos dados pessoais do sistema. Proteja-os com o mesmo cuidado e apague-os ao fim do prazo de retenção (ver LGPD abaixo).

### Ensaio de restauração

Faça este ensaio **antes** de pôr dados reais e repita a cada três meses, numa VPS de teste com o mesmo `.env.prod`:

```bash
osint up -d postgres neo4j      # cria volumes vazios
osint stop neo4j

# PostgreSQL
osint exec -T postgres pg_restore -U flowsint -d flowsint --clean --if-exists < backup/pg-AAAA-MM-DD.dump

# Neo4j
cp backup/neo4j-AAAA-MM-DD.dump backup/neo4j.dump
docker run --rm -v osintbrflow_neo4j_data_prod:/data -v "$PWD/backup":/backups \
  neo4j:5 neo4j-admin database load neo4j --from-path=/backups --overwrite-destination=true

# Painel Brasil
osint up -d api
osint cp backup/brasil-AAAA-MM-DD.sqlite3 api:/home/flowsint/brasil-data/brasil.sqlite3
osint restart api celery

osint up -d
```

Confira: login de uma conta conhecida, um sketch com o grafo, um caso Brasil com o pacote de evidências exportado e verificado.

Os nomes de volume (`osintbrflow_...`) vêm do nome do projeto em `compose.br.yml`. Confirme com `docker volume ls`. Os comandos de backup e restauração **não foram executados** nesta entrega; ajustes de permissão (o usuário do Neo4j no container) podem ser necessários no primeiro ensaio.

## Atualizações

```bash
# 1. Backup completo (seção anterior)
# 2. Código novo
git pull
python3 scripts/init-prod.py --check
# 3. Recompilar e subir; as migrações do PostgreSQL rodam sozinhas na API
osint up -d --build
osint ps
# 4. Limpeza de imagens antigas
docker image prune -f
```

Atualize também o sistema operacional (`sudo apt update && sudo apt upgrade`) e as imagens base: `osint pull` baixa novas versões de PostgreSQL 15, Neo4j 5, Redis 7 e Caddy 2.11 dentro das mesmas versões principais.

## O laboratório não se hospeda

**O laboratório Brasil (`compose.lab.yml`, porta 8000) não tem login. Não o publique na internet, nem atrás deste Caddy, nem com túneis (ngrok, Cloudflare Tunnel etc.).**

Proteções existentes e seus limites:

- `compose.lab.yml` publica a porta só em `127.0.0.1`.
- O laboratório recusa nomes de host que não sejam `localhost`, `127.0.0.1` ou `::1` (defesa contra DNS rebinding).
- **Novo nesta entrega:** no modo local, o laboratório recusa conexões vindas de **endereços IP públicos** (resposta 403), mesmo que o atacante envie `Host: localhost`. Isso cobre o erro de publicar a porta em `0.0.0.0` numa VPS.
- **Não cobre:** acesso pela rede local (Wi-Fi do escritório, VPN), um proxy reverso na mesma máquina ou túneis. Nesses casos o laboratório vê um endereço privado e não tem como saber que a requisição veio de fora. Por isso a regra continua sendo: não exponha.

O modo Colab é outra coisa: exige uma chave por sessão e só existe enquanto o notebook estiver aberto.

## Limites das fontes públicas (BrasilAPI, ViaCEP, IBGE)

As consultas do painel Brasil vão a serviços **gratuitos e públicos**, mantidos por voluntários (BrasilAPI) ou por órgãos públicos. Hoje o OsintbrFLOW:

- não guarda cache das respostas;
- tenta de novo **uma vez** após erro 429 ou 5xx, com espera de 0,25 s;
- não limita quantas consultas a equipe faz por minuto.

Com várias pessoas no mesmo servidor, todas as consultas saem do **mesmo IP**. Se esse IP for bloqueado, todos ficam sem as fontes. Combine na equipe:

- consultar identificadores um de cada vez, ligados a um caso com finalidade definida;
- não usar o sistema para varreduras em lote ou listas longas de CNPJs/CEPs;
- quando a fonte responder "indisponível", esperar antes de repetir;
- para volume alto, usar bases oficiais baixadas (dados abertos da Receita Federal, IBGE) em vez de APIs públicas.

## Lista de conferência de segurança

Antes de pôr dados reais:

- [ ] `python3 scripts/init-prod.py --check` aprovado; `.env.prod` com permissão 600 e cópia no cofre
- [ ] `FLOWSINT_ALLOW_REGISTRATION=false` e teste do `curl` devolvendo 403
- [ ] `ss -tlnp` na VPS mostra só 22, 80 e 443 abertas para fora (5432, 6379, 7474, 7687, 5001, 5173 e 8000 **não** podem aparecer em `0.0.0.0`)
- [ ] `compose.lab.yml` **não** está rodando nesta máquina
- [ ] `https://` abre com certificado válido; `http://` redireciona para `https://`
- [ ] Cabeçalhos presentes: `curl -sI https://osint.suaorg.com.br | grep -iE 'strict-transport|nosniff|frame|referrer'`
- [ ] SSH só com chave (`PasswordAuthentication no`), sem login de root
- [ ] Atualizações automáticas de segurança do sistema ligadas (`unattended-upgrades`)
- [ ] Backup feito **e** ensaio de restauração concluído
- [ ] Equipe orientada sobre senhas longas, finalidade dos casos e uso moderado das fontes públicas
- [ ] Alguém responsável por acompanhar avisos de segurança do Flowsint upstream e deste fork

## LGPD — o mínimo para começar

Este sistema trata dados pessoais (nomes, endereços, vínculos societários, e-mails das contas, IPs nos logs). A organização que hospeda é **controladora** desses dados. O que segue é um ponto de partida operacional; **não substitui** orientação jurídica nem o encarregado (DPO) da organização.

**Base legal.** Antes de usar, registre qual base legal do art. 7º (e, se houver dados sensíveis, do art. 11) sustenta cada tipo de investigação: por exemplo, legítimo interesse com teste de balanceamento documentado, cumprimento de obrigação legal, exercício regular de direitos em processo. "É dado público" não dispensa base legal nem finalidade (art. 7º, §§ 3º e 4º).

**Finalidade por caso.** O painel Brasil já exige o campo **finalidade** ao criar um caso, e ele vai para o pacote de evidências exportado. Use-o de verdade: descreva o motivo concreto ("due diligence do fornecedor X para contrato Y"), não "investigação". Os sketches nativos do Flowsint não têm esse campo: registre a finalidade na descrição da investigação.

**Minimização.** Consulte só o necessário para a finalidade. O sistema recusa CPF de propósito; não contorne isso.

**Retenção.** Defina um prazo (por exemplo, 12 meses após o encerramento do caso) e revise a cada trimestre. Os backups seguem o mesmo prazo: backup antigo também precisa ser apagado.

**Exclusão.** Hoje:

- investigações e sketches nativos podem ser apagados pela interface;
- **casos do painel Brasil não têm botão de exclusão**. É preciso apagar direto no banco SQLite, com o sistema no ar, por quem administra o servidor:

  ```bash
  osint exec -T api python -c "import sqlite3,sys; d=sqlite3.connect('/home/flowsint/brasil-data/brasil.sqlite3'); d.execute('PRAGMA foreign_keys=ON'); d.execute('DELETE FROM runs WHERE case_id=?',(sys.argv[1],)); d.execute('DELETE FROM cases WHERE id=?',(sys.argv[1],)); d.commit(); d.execute('VACUUM')" ID_DO_CASO
  ```

- **contas de usuário não têm exclusão pela interface** (só por SQL no PostgreSQL);
- os dados continuam nos backups até eles vencerem.

**Logs.** O Caddy registra IP, data, método e caminho de cada acesso; API e nginx registram caminhos. Os logs ficam nos containers com rotação de 5 arquivos de 10 MB por serviço, e somem quando o container é recriado. Se precisar guardar logs para auditoria, exporte-os para um local com acesso restrito e prazo definido.

**Quem acessa.** Todas as contas têm o mesmo nível. Quem tem SSH na VPS ou o `.env.prod` acessa **tudo**, inclusive dados de outras pessoas. Mantenha uma lista nominal de quem tem conta e quem tem acesso ao servidor, e revise quando alguém sair da equipe (sem exclusão de conta pela interface, troque a senha da conta e desative-a no banco: `UPDATE profiles SET is_active=false ...`; confira se o upstream respeita `is_active` antes de confiar nisso — nesta revisão o login não verifica esse campo).

**Titulares.** Tenha um canal para pedidos de titulares (acesso, correção, eliminação) e saiba localizar os dados de uma pessoa nos três armazenamentos.

## O que não está feito

- **Sem limitação de taxa (rate limiting) no login nem na API.** O Caddy oficial não traz esse módulo; seria preciso compilar o Caddy com o plugin `caddy-ratelimit` (via `xcaddy`) ou usar fail2ban lendo os logs do Caddy. Nenhuma das opções foi configurada ou testada.
- **Sem WAF** (firewall de aplicação).
- **Sem SSO, 2FA ou RBAC granular.** Login por e-mail e senha, sem papel de administrador e sem política de senha.
- **Sessões longas:** o token de login vale 60 horas e não pode ser revogado individualmente. Trocar `AUTH_SECRET` desconecta todo mundo.
- **Sem armazenamento WORM** nem cadeia de custódia jurídica. Quem controla o servidor pode alterar os dados; os hashes do pacote detectam alterações no pacote, não impedem reescrita.
- **Sem backup automático, monitoramento ou alertas.** Os comandos acima são manuais.
- **Sem criptografia em repouso** além da que o provedor da VPS oferecer no disco. As chaves de API salvas são cifradas com `MASTER_VAULT_KEY_V1`; o resto não.
- **Sem cache nem cota** para as fontes públicas.
- **Sem exclusão de caso Brasil nem de conta pela interface.**
- **Sem deploy real executado** até a data no topo deste documento.
