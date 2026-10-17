# RELATÓRIO DE TESTES — SÓSIA 1.2.0

Data: 2026-10-17 11:03 UTC  
Ambiente: nuvem (sandbox Linux da Anthropic) — `Linux-6.18.44-fc-v139-x86_64-with-glibc2.39`

## Matriz de versões do Python

| Versão | Testes | Resultado | Tempo |
|---|---|---|---|
| Python 3.9.25 | 36 | **PASSOU** | 0.198 s |
| Python 3.10.20 | 36 | **PASSOU** | 0.228 s |
| Python 3.11.17 | 36 | **PASSOU** | 0.248 s |
| Python 3.12.3 | 36 | **PASSOU** | 0.242 s |
| Python 3.13.16 | 36 | **PASSOU** | 0.246 s |
| Python 3.14.6 | 36 | **PASSOU** | 0.201 s |

Comando: `python -I -W error::ResourceWarning -m unittest discover -s tests -v`

## Testes executados (Python 3.13)

| Teste | O que garante | Status |
|---|---|---|
| `test_semantica_sherlock` | Checagem ao vivo segue as regras do Sherlock (status, mensagem, redirecionamento, listas, bloqueios) | ok |
| `test_site_inacessivel_e_descartado` | Plataforma inacessível é descartada em vez de gerar resultados falsos | ok |
| `test_site_que_mente_e_descartado` | Plataforma que diz 'existe' para nome impossível é descartada (anti soft-404) | ok |
| `test_sonda_tem_prioridade` | Usa a URL de sonda do Sherlock quando ela existe | ok |
| `test_varredura_e_achados` | Varredura encontra o sósia registrado e classifica o risco | ok |
| `test_combinada_entra_no_padrao_e_e_alto` | Combinadas entram nas 60 variantes padrão com risco ALTO | ok |
| `test_homoglifo_mais_isca` | Técnica combinada: homóglifo + isca (banc0aurora_suporte) | ok |
| `test_demo_gera_pivo_evidencias_denuncia_e_stix` | Caso demo: 1 pivô, 7 evidências com hash conferido no manifesto, denúncia com canais oficiais | ok |
| `test_prova_da_leitura` | Toda página lida gera prova: status, hora UTC e SHA-256; falha de rede não gera prova | ok |
| `test_stix_bem_formado_e_deterministico` | STIX 2.1 sem referência quebrada e com o mesmo ID para a mesma conta em buscas diferentes | ok |
| `test_acha_execucao_anterior_na_pasta` | Acha a última busca completa da mesma marca, ignorando 'só gerar' e outras marcas | ok |
| `test_duas_execucoes_reais_pela_linha_de_comando` | Duas buscas seguidas pela linha de comando: pastas separadas e 0 novos na segunda | ok |
| `test_sem_anterior` | Primeira execução: nada marcado como novo | ok |
| `test_sumiu_so_onde_foi_verificado` | 'Sumiu' só vale onde a plataforma foi verificada agora; plataforma descartada não gera falso 'sumiu' | ok |
| `test_acento_nao_atrapalha` | Acentos e pontuação não atrapalham a comparação (Bánco Áurora = bancoaurora; promoção = promocao) | ok |
| `test_avaliacao` | Classificação CRÍTICA: nome igual, marca + PIX; fã com a marca no nome não é crítico; pessoa comum não gera sinal | ok |
| `test_extrai_nome_e_bio_nas_duas_ordens` | Lê nome e bio das etiquetas og:, em qualquer ordem de atributos, e limpa '(@usuario) • Instagram' | ok |
| `test_pagina_de_login_nao_conta_como_perfil` | Página de login ('Instagram') e erro 404 não contam como perfil legível | ok |
| `test_titulo_quando_nao_ha_og` | Sem etiquetas og:, usa o título da página | ok |
| `test_contato_compartilhado_liga_e_contamina` | Contato repetido liga dois sósias, e quem divide contato com um CRÍTICO vira CRÍTICO | ok |
| `test_contato_oficial_nao_conta` | Contato publicado pelo próprio perfil oficial não liga ninguém | ok |
| `test_ignora_plataformas_cpf_e_texto_comum` | Não extrai links das próprias plataformas, CPF (LGPD) nem números comuns do texto | ok |
| `test_outros_tipos` | Extrai chave PIX aleatória, e-mail, Telegram, CNPJ, encurtador (com caminho) e site (só domínio) | ok |
| `test_whatsapp_e_telefone_viram_o_mesmo_numero` | wa.me, (31) 90000-0000 e +55 31 9 0000-0000 viram o mesmo número normalizado | ok |
| `test_cli_demo` | Linha de comando --demo roda do início ao fim e gera a pasta de resultados | ok |
| `test_demo_ponta_a_ponta` | Caso demo completo: 7 sósias, 3 CRÍTICOS, Kick descartado, 3 novos e 1 sumido, hashes conferem | ok |
| `test_html_escapa` | Relatório HTML neutraliza código malicioso vindo de nomes | ok |
| `test_lista_padrao` | Lista padrão de plataformas carrega | ok |
| `test_so_gerar_nao_acessa_rede` | Modo --so-gerar não faz nenhum acesso à rede | ok |
| `test_destaque` | Destaca no relatório exatamente os caracteres que mudaram | ok |
| `test_homoglifos_de_duas_letras` | Trocas de duas letras: m↔rn, d↔cl, w↔vv | ok |
| `test_limite_e_prioridade` | Respeita o limite --max e põe as variantes mais perigosas primeiro | ok |
| `test_rodizio_mantem_variedade` | Com o limite padrão, todas as técnicas aparecem | ok |
| `test_sem_repeticao_e_sem_original` | Nenhuma variante repetida e o próprio original nunca entra na lista | ok |
| `test_separadores_existentes` | Troca e remove pontos, sublinhados e hífens já existentes | ok |
| `test_tecnicas_basicas` | Gera as seis técnicas: homóglifo, isca, separador, duplicação, omissão e troca | ok |

## Ponta a ponta pela linha de comando

`python sosia.py --demo --sem-abrir` → **PASSOU**

```
Relatório: /tmp/claude-0/e2e_sosia/sosia_bancoaurora_20261017-110325/relatorio.html
Kit de denúncia: /tmp/claude-0/e2e_sosia/sosia_bancoaurora_20261017-110325/denuncia.md
```

## O que NÃO foi testado aqui (faça na sua máquina)

- **Consulta real à internet.** A rede deste ambiente de nuvem bloqueia as plataformas. Toda a lógica foi validada com respostas simuladas fiéis ao formato real; o primeiro teste ao vivo deve ser feito com um nome que você conhece (o seu, por exemplo).
- **Leitura de perfis reais.** Quais plataformas mostram nome de exibição e bio a visitantes (sem login) muda com frequência; a extração foi testada com páginas no formato público (etiquetas og:), não com as plataformas ao vivo.
- **Lançadores de Windows e macOS** (`.bat` e `.command`). O `.sh` foi executado no Linux; os outros dois têm a mesma lógica, mas não foram rodados nesses sistemas.
- **Mudanças nas plataformas.** Sites mudam de layout e regras com frequência; a lista de sites vem do Sherlock e pode ser atualizada trocando o arquivo (veja o manual).
