# Roadmap orientado a capacidade investigativa

## Entregue — alpha 0.1.0

Fork preservado; workspace BR; três APIs; três tipos e três enrichers nativos; quatro percursos; evidências por caso; diff; verificação de pacotes; exportação para grafo Flowsint; atlas com distinção de acesso; testes e modo sintético.

## 0.2 — Contratações públicas e interoperabilidade

1. Conector PNCP com paginação, orçamento de chamadas e cobertura temporal explícita. CNPJ de fornecedor e CNPJ de órgão são papéis diferentes.
2. Ingestão de arquivos de dados abertos da Receita, sem enumerar pessoas. Versionamento por competência e reconciliação por identificador.
3. Importação SpiderFoot JSON/eventos como observações externas com referência ao scan e licença preservada.
4. Fixar dívida TypeScript upstream e executar o stack completo em CI com PostgreSQL, Redis e Neo4j.

**Aceite:** fixtures de sucesso/erro/paginação; consulta real reproduzível; trilha CNPJ → contrato → órgão → município; nenhuma aresta sem fonte.

## 0.3 — Grafo de hipóteses e revisão

1. Separar observação, hipótese, contraevidência e conclusão aprovada.
2. Evidência negativa com escopo: o que foi consultado, quando, com qual cobertura e quais limitações.
3. Resolver possíveis duplicidades com fila de revisão, sem merges automáticos por nome, CEP, ASN ou endereço compartilhado.
4. Gerar relatório determinístico por caso com afirmações ligadas aos IDs de evidência.

**Aceite:** cada conclusão tem evidências e alternativas; hipóteses rejeitadas continuam auditáveis; zero escore de culpa.

## 0.4 — Tempo, cobertura e cooperação

1. Agendamento persistente com Celery, cancelamento, retry por fonte e circuit breaker.
2. Linha do tempo com tempo do evento, tempo de publicação e tempo de coleta distintos.
3. Matriz de cobertura por fonte/UF/município/período. Ausência de cobertura deve ser visível.
4. Papéis de caso, compartilhamento explícito, política de retenção, exclusão e backups testados.

**Aceite:** reinício de worker não perde execução; caso não vaza para outro usuário; falha de uma fonte não desaparece do histórico.

## 0.5 — Assistência de IA fundamentada

LLM opcional para propor próximo passo e resumir evidências, sem criar fatos. Toda afirmação exige ID existente e conteúdo correspondente. Dados externos são tratados como conteúdo não confiável; nenhum documento pode instruir o agente a executar ferramentas. Controle de envio a serviços externos por caso.

**Aceite:** benchmark de citações inexistentes, contradições, homônimos e prompt injection; modelo pode se abster; análise humana permanece separada da observação.

## Medir antes de dizer “superior”

- Tempo mediano e p95 para concluir os mesmos cenários BR em Flowsint e OsintbrFLOW.
- Proporção de arestas com fonte recuperável; erros de merge e de interpretação de ausência.
- Facilidade de instalar em máquina limpa; recuperação de backup; import/export sem perda.
- Memória, latência e fluidez em grafos de 1k/10k/100k nós — ainda não medidos.
- Taxa de sucesso dos conectores, qualidade dos contratos e completude do relatório.

O objetivo é reduzir o trabalho de verificar uma hipótese brasileira e aumentar a capacidade de auditar como a conclusão foi construída, não maximizar o número de links ou animações.
