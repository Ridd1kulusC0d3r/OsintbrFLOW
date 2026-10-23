# Changelog do SÓSIA

## 1.3.0 · 2026-10-22

**Pronto para uso real e para rodar agendado.**

- **Um só fluxo.** `executar()` faz a busca inteira e é usado pela linha de comando e pelo enriquecedor do OsintbrFLOW. Antes, cada um montava as etapas do seu jeito.
- **Linha de comando com `argparse`.** Ajuda em português, validação de `--max` (de 1 a 500) e erro de uso com código 1.
- **Contas oficiais (`--oficiais a,b`).** Contas reserva e regionais da própria marca nunca viram sósia, e o limite de variantes continua cheio. O modo guiado pergunta por elas.
- **Filtro de plataformas (`--plataformas Instagram,TikTok`)**, que avisa quando um nome não existe e lista as disponíveis.
- **`--extra`.** Junta X (Twitter), Pinterest, Reddit, Snapchat e Patreon (`sites_extra.json`, copiado sem modificação do Sherlock).
- **Espera quando a plataforma limita.** Em 429 ou 503, o SÓSIA respeita o `Retry-After` (até 8 s) e tenta de novo uma vez. Se o limite continuar, o resultado vira "?", nunca "livre". Depois de 5 bloqueios seguidos na mesma plataforma, o SÓSIA para de insistir nela, marca o restante como "?" e registra a plataforma como "incompleta" no relatório. Isso evita minutos de espera e não piora o bloqueio.
- **`--alerta` para agendamento.** Sai com código 2 quando há CRÍTICO ou ALTO novo (ou CRÍTICO na primeira busca) e imprime uma linha `ALERTA:` para o agendador ou o e-mail.
- **Robustez.** O modo guiado não quebra sem teclado (agendador, pipe) e Ctrl+C sai limpo (código 130).
- **Regras conferidas.** As 12 plataformas são idênticas ao `data.json` do Sherlock no commit `e40a45e` (26/09/2026).
- **OsintbrFLOW:** o enriquecedor ganhou os parâmetros `oficiais` e `plataformas`.
- **Testes:** de 36 para 45, incluindo uma busca completa pela rede de verdade (`urllib`) contra um servidor HTTP local que imita cinco plataformas: status, mensagem, redirecionamento, soft-404 e 429 com `Retry-After`.

## 1.2.0 · 2026-10-17

**Ligar, provar e denunciar.** A 1.1 dizia quem imita. A 1.2 diz quem é da mesma operação, guarda a prova e prepara a denúncia.

- **Pivôs de contato.** O SÓSIA tira das bios telefone/WhatsApp (`wa.me` e celular brasileiro em qualquer escrita), e-mail, chave PIX aleatória, CNPJ, Telegram e links. Tudo é normalizado, para que o mesmo número escrito de dois jeitos seja reconhecido. Um contato repetido em dois ou mais sósias vira pivô, e quem divide contato com um CRÍTICO também vira CRÍTICO. Contatos publicados pelo perfil oficial não contam, e CPF não é extraído (LGPD). Saída: seção no relatório e `contatos.csv`.
- **Evidência com cadeia de custódia.** Cada página lida fica em `evidencias/`, exatamente como chegou, com HTTP, hora UTC e SHA-256, também listados no `manifesto.txt`. Os arquivos terminam em `.html.txt` para nunca executar script de página de golpista.
- **Kit de denúncia.** `denuncia.md` com o canal oficial de cada plataforma (conferidos em outubro de 2026: formulário do Instagram, política do YouTube, @notoscam do Telegram, formulário de marca do TikTok, página de abuso do GitHub). Para cada CRÍTICO e ALTO, traz os sinais, a evidência e um texto montado só com o que foi encontrado.
- **STIX 2.1.** `achados.stix.json` para OpenCTI e MISP, com identidade do original, `user-account` por sósia, relação `impersonates`, notas e agrupamento. Os IDs são determinísticos e foram conferidos contra a biblioteca `stix2` da OASIS.
- **Relatório:** placar de pivôs, contatos em cada perfil e a lista "Arquivos desta busca".
- **OsintbrFLOW:** o enriquecedor `username_to_impersonators` cria nós `Phone` e `Email` (`PUBLISHES_CONTACT`) e guarda em cada conta o hash e a hora da coleta.
- **Documentação:** README com imagens e diagramas, manual atualizado (novas seções, telas anotadas, glossário) e guia interativo O Caso Banco Aurora.
- **Caso demo:** o golpista publica o mesmo WhatsApp no Instagram e no Telegram, escrito de dois jeitos.
- **Testes:** de 28 para 36. Rodam em Python 3.9 a 3.14.

## 1.1.0 · 2026-10-11

- Técnica combinada (homóglifo + isca: `banc0aurora_suporte`).
- Leitura de nome de exibição e bio, com o nível CRÍTICO.
- Monitoramento automático NOVO / SUMIU e `mudancas.csv`.
- Integração ao OsintbrFLOW (`username_to_impersonators`).

## 1.0.0 · 2026-10-09

- Primeira versão: 6 técnicas de variantes, 12 plataformas no formato Sherlock, linha de base anti soft-404, relatório HTML, CSV e manifesto SHA-256.
