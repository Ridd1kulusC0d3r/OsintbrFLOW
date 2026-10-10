# OSINT Brasil Flow — comece aqui

O OSINT Brasil Flow é um laboratório de investigação em fontes abertas que roda **só no seu computador**. Você cria um caso, informa um CNPJ, um CEP ou um município e o programa consulta fontes públicas (BrasilAPI, ViaCEP e IBGE). Cada resultado vira uma evidência com data, origem e uma "impressão digital" (SHA-256), ligada às outras num grafo que você pode exportar e conferir depois.

Não precisa instalar Python, Node nem criar conta. Também não precisa de chave de API.

**Manual ilustrado:** abra `manual/index.html` (nesta mesma pasta) no navegador. Tem capturas de tela do painel, tutorial do caso demonstrativo, solução de problemas e glossário, e funciona sem internet. Também está em https://github.com/Ridd1kulusC0d3r/OsintbrFLOW/blob/main/docs/manual/index.html

## Como abrir

Primeiro, **extraia o arquivo .zip inteiro** para uma pasta (por exemplo, Documentos). Não abra o programa de dentro do .zip.

| Sistema | O que fazer |
|---|---|
| **Windows** | Dê dois cliques em **Abrir OsintbrFLOW.bat** |
| **macOS** | Clique com o botão direito em **Abrir OsintbrFLOW.command** → **Abrir** (só da primeira vez; depois, dois cliques) |
| **Linux** | Dê dois cliques em **abrir-osintbrflow.sh** (se o gerenciador de arquivos perguntar, escolha "Executar"). No terminal: `./abrir-osintbrflow.sh` |

Abre uma janela de texto (o "motor" do laboratório) e, em seguida, o painel: numa janela própria ou no seu navegador. **Deixe a janela de texto aberta** enquanto usa o painel. Para encerrar, feche o painel e depois a janela de texto (ou pressione Ctrl+C nela).

Primeira vez? No painel, comece em **Explorar caso demonstrativo**: ele usa dados de exemplo e não acessa a internet.

## Avisos de "aplicativo não verificado"

Este aplicativo é gratuito e ainda não tem assinatura digital paga da Microsoft ou da Apple. Por isso, o sistema mostra um aviso na primeira vez. É esperado.

**Windows (SmartScreen):** aparece "O Windows protegeu o computador". Clique em **Mais informações** → **Executar assim mesmo**.

**macOS (Gatekeeper):** aparece "não pode ser aberto porque é de um desenvolvedor não identificado".

1. Clique com o botão direito (ou Control + clique) em **Abrir OsintbrFLOW.command** e escolha **Abrir**. Confirme em **Abrir**.
2. Se ainda assim não abrir: vá em **Ajustes do Sistema → Privacidade e Segurança**, role até o fim e clique em **Abrir Mesmo Assim** ao lado do aviso sobre o OsintbrFLOW. Depois abra de novo.

Só faça isso se você baixou o arquivo da página oficial de Releases do projeto. Para conferir, compare o SHA-256 do .zip com o arquivo `SHA256SUMS.txt` publicado junto.

## Onde ficam os casos

Os casos ficam num arquivo do seu usuário, fora da pasta do aplicativo. Você pode apagar ou atualizar o aplicativo sem perder casos.

| Sistema | Pasta |
|---|---|
| Windows | `%APPDATA%\OsintbrFLOW` (ex.: `C:\Users\voce\AppData\Roaming\OsintbrFLOW`) |
| macOS | `~/Library/Application Support/OsintbrFLOW` |
| Linux | `~/.local/share/osintbrflow` |

A janela de texto mostra o caminho exato ao abrir ("Casos guardados em: …").

## Como exportar um caso

No painel, abra o caso e use **Exportar evidências**. Você recebe um pacote JSON com todas as coletas, as evidências e os hashes encadeados. Esse pacote pode ser conferido depois na própria ferramenta (**Verificar pacote**), em outro computador.

O hash mostra que o conteúdo não foi alterado depois da coleta. Ele **não** comprova que a informação é verdadeira, quem é o autor nem substitui uma cadeia de custódia jurídica.

## O que o programa recusa

- **CPF e dados de pessoa física.** Se você digitar algo com formato de CPF, o programa recusa antes de qualquer consulta externa e não grava o valor.
- Qualquer entrada fora de CNPJ, CEP ou código de município.

## Segurança: não exponha à internet

O laboratório **não tem login**. Por isso ele só aceita conexões do próprio computador (endereço `127.0.0.1`) e não existe opção para mudar isso. Não tente publicá-lo com redirecionamento de porta, túnel ou servidor web: qualquer pessoa que alcançasse o painel veria e alteraria seus casos.

## Como desinstalar

1. Feche o laboratório.
2. Apague a pasta onde você extraiu o .zip.
3. Se quiser apagar também os casos, apague a pasta de dados indicada acima. **Isso é definitivo:** exporte antes o que quiser guardar.

## Prefere instalar pelo Python?

Se você já usa Python 3.12 ou mais novo, baixe o arquivo `osintbrflow-….whl` da mesma página de Releases e rode:

```bash
pipx install ./osintbrflow-0.2.0-py3-none-any.whl
osintbr
```

Na pasta `pipx` deste pacote há lançadores de dois cliques que chamam o comando `osintbr` instalado assim.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| Nada acontece ao dar dois cliques | Confira se extraiu o .zip inteiro e se o lançador está ao lado da pasta `OsintbrFLOW` |
| "Janela própria indisponível; abrindo no navegador" | Normal em alguns sistemas. O painel funciona igual no navegador |
| O navegador não abriu | Copie o endereço `http://127.0.0.1:…/brasil.html` mostrado na janela de texto e cole no navegador |
| Antivírus bloqueou | Aplicativos sem assinatura às vezes geram alerta falso. Confira o SHA-256 e, se bater, libere o arquivo |
| Fonte aparece com ⚠️ | A fonte pública estava fora do ar ou bloqueada pela sua rede naquele momento. Isso **não** quer dizer que o registro não existe |

Código, documentação e limitações: https://github.com/Ridd1kulusC0d3r/OsintbrFLOW
