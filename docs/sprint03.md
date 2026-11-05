# Sprint 03 — Coleta e armazenamento de dados

**Projeto fictício:** CandleVault  
**Diretório sugerido:** `candlevault`  
**Etapa de estudo:** 3 — Coleta e armazenamento de dados  
**Objetivo:** criar um importador didático de candles fictícios em JSON para SQLite, com validação, precisão decimal, idempotência e identificação de lacunas.

O CandleVault é independente dos projetos SpotLab, PySpot e do robô principal. Nesta sprint, a fonte de coleta será um arquivo local: primeiro serão estudados os contratos e a qualidade dos dados; uma futura integração com API poderá reutilizar esses conceitos.

## 1. Conhecimentos trabalhados

| Conhecimento | Aplicação no exemplo |
| --- | --- |
| Ingestão de JSON | Receber snapshots fictícios de candles |
| `Decimal` e horários UTC | Preservar precisão e identidade temporal |
| Validação de domínio | Conferir preços, volume, duração e OHLC |
| SQLite e transações | Persistir dados sem gravar parcialmente um lote com falha técnica |
| Chave composta | Impedir duplicações da mesma origem, par e intervalo |
| Idempotência | Reprocessar um arquivo sem alterar os dados já aceitos |
| Política de atualização | Atualizar candles abertos e proteger candles fechados |
| Consulta e lacunas | Ordenar registros e identificar intervalos ausentes |

## 2. Resultado esperado

Uma aplicação de terminal que importe arquivos locais, apresente contagens auditáveis, consulte candles em ordem cronológica e detecte lacunas. Deve incluir dados fictícios, testes automatizados, glossário e roteiro de validação.

## 3. Prompt autossuficiente de execução

Copie o bloco abaixo para o agente responsável pela implementação. Não é necessário consultar documentos das etapas anteriores.

````text
Você é um desenvolvedor Python experiente. Implemente a Sprint 03 do projeto fictício CandleVault: um laboratório local de coleta, validação e armazenamento de candles em SQLite.

OBJETIVO E DIRETÓRIO

O usuário conhece Java, APIs e bancos de dados e está aprendendo os fundamentos de um robô de criptomoedas. Implemente código e documentação, não apenas um plano.

Trabalhe em um diretório próprio chamado candlevault dentro do diretório indicado pelo usuário ou, na ausência de indicação, dentro do diretório atual. Se existir, inspecione e preserve trabalho alheio. Não altere projetos vizinhos. Não importe módulos do SpotLab, PySpot ou de outro projeto.

TECNOLOGIA E ESCOPO

- Python 3.11 ou superior e apenas biblioteca padrão: json, decimal, datetime, sqlite3, argparse, unittest e outras estritamente necessárias.
- Fonte local JSON com dados fictícios; execução sem rede, credenciais, Binance ou envio de ordens.
- Somente candles de um minuto, intervalo identificado por "1m". Rejeite outros intervalos explicitamente.
- Origem fictícia "FICTICIA", par "BTCUSDT" e volume do ativo base em BTC nos exemplos. A identidade deve incluir a origem para evitar colisões entre fontes.
- Não implemente estratégias, indicadores, backtest, WebSocket, agendamento, banco remoto, Parquet, interface web, Docker ou AWS.
- Diferencie candle, trade, bid/ask e livro de ofertas no glossário. Apenas candles serão importados nesta sprint.

ARQUITETURA SIMPLES

Separe leitura JSON, conversão/validação, regras de atualização, repositório SQLite e interface de terminal. Evite frameworks e abstrações sem uso concreto.

Use dataclasses e anotações de tipo onde ajudarem. O núcleo não deve imprimir mensagens. Injete um relógio na camada de ingestão para registrar recebimento; nos cenários e testes, use um relógio fixo. O CLI normal pode usar datetime.now(timezone.utc).

CONTRATO DO ARQUIVO

Use um objeto com schema_version igual ao inteiro 1 e candles como lista de objetos. Cada candle deve conter exatamente os campos documentados:

{
  "schema_version": 1,
  "candles": [
    {
      "source": "FICTICIA",
      "symbol": "BTCUSDT",
      "interval": "1m",
      "open_time": "2026-11-05T12:00:00+00:00",
      "close_time": "2026-11-05T12:01:00+00:00",
      "open": "100000.00",
      "high": "100100.00",
      "low": "99900.00",
      "close": "100050.25",
      "volume": "0.125",
      "is_closed": true,
      "snapshot_at": "2026-11-05T12:01:00+00:00"
    }
  ]
}

Defina close_time como fim EXCLUSIVO do intervalo [open_time, close_time). Esta é uma convenção do laboratório, não um mapeamento direto de uma API externa.

snapshot_at é o instante fictício em que a fonte observou aquela versão do candle. received_at será gerado pela aplicação ao receber um registro aceito; não vem do JSON. Diferencie início/fim do candle, snapshot da fonte e recebimento local.

VALIDAÇÃO

- Arquivo ilegível, JSON malformado, chaves duplicadas, versão não suportada ou estrutura superior inválida: rejeite a importação inteira, com saída diferente de zero e sem alteração dos dados.
- Não aceite constantes JSON não padronizadas NaN/Infinity nem schema_version booleano.
- Registro inválido dentro de uma lista estruturalmente válida: rejeite somente o registro, com índice e motivo; continue os demais.
- Exija strings decimais com ponto, sem separador de milhares. Converta diretamente para Decimal, sem float. Rejeite vazio, texto malformado, NaN, sNaN e infinitos.
- Preços positivos; volume não negativo. Garanta low <= high, low <= open <= high e low <= close <= high.
- is_closed deve ser booleano real, não string ou inteiro.
- Identificadores não vazios, sem espaços nas extremidades; não normalize silenciosamente símbolos inconsistentes. Documente o conjunto admitido no laboratório.
- Datas ISO 8601 com fuso obrigatório; normalize para UTC. Datas sem fuso são inválidas.
- Abertura alinhada ao minuto UTC, fim exatamente um minuto depois e snapshot_at >= open_time.
- Se fechado, snapshot_at >= close_time; se aberto, open_time <= snapshot_at < close_time. Trata-se de convenção didática para snapshots da fonte.
- Para um mesmo candle aberto, rejeite atualização que altere a abertura de preço, reduza high, aumente low ou reduza volume. Close pode variar dentro dos limites. Explique que se pressupõem snapshots cumulativos sem correções da fonte.

PERSISTÊNCIA E PRECISÃO

Crie o schema automaticamente em banco informado pelo usuário; use SQL parametrizado e feche conexões corretamente.

Chave primária composta: source, symbol, interval, open_time. Armazene datas UTC com representação canônica de largura fixa, incluindo microssegundos e +00:00, para que igualdade e ordenação sejam consistentes.

Armazene open, high, low, close e volume como TEXT. Ao consultar, reconstrua Decimal. Não utilize REAL, CAST AS REAL, soma ou comparação textual de preços para cálculos financeiros. Documente a limitação da representação textual no SQL.

Mantenha também close_time, is_closed, snapshot_at, received_at e uma tabela ou registro de resumo de cada importação com suas contagens. Não é necessário guardar o arquivo bruto nem todas as versões dos candles.

Idempotência deve comparar valores decimais numericamente: "100000.0" e "100000.00" representam o mesmo valor. Não deixe a formatação textual decidir se houve mudança. Ordene consultas por open_time dentro da origem/par/intervalo selecionados.

POLÍTICA DE ATUALIZAÇÃO

Cada registro deve receber exatamente uma classificação: inserido, atualizado, ignorado ou rejeitado.

1. Chave inexistente: inserir registro válido.
2. Conteúdo de domínio e snapshot_at numericamente/temporalmente equivalentes: ignorar, sem mudar received_at ou outros campos do candle.
3. Registro existente aberto e snapshot mais antigo: ignorar como obsoleto.
4. Mesmo snapshot_at com conteúdo divergente: rejeitar como conflito, sem sobrescrever.
5. Registro existente aberto e snapshot mais recente: atualizar se passar pelas validações cumulativas; pode permanecer aberto ou tornar-se fechado.
6. Registro existente fechado: se o conteúdo de domínio for igual, ignorar; se houver mudança de OHLCV, horários do intervalo ou tentativa de reabrir, rejeitar como conflito. Não permita correção automática de candle fechado nesta sprint.

Defina e documente a precedência das regras: duplicação exata, proteção de fechado, snapshot obsoleto, conflito no mesmo snapshot e atualização. Diferença apenas em snapshot_at de um candle fechado com conteúdo igual é ignorada. Atualização aceita de candle aberto com snapshot posterior deve registrar o novo snapshot_at e received_at mesmo se OHLCV não mudou.

Processe registros na ordem do arquivo. Duplicatas dentro do próprio lote devem seguir as mesmas regras de registros de lotes anteriores.

TRANSAÇÕES E RELATÓRIO

- Use uma transação por importação para alterações aceitas e resumo. Rejeições de domínio não impedem persistir os registros válidos.
- Erro técnico durante a gravação deve desfazer todas as alterações e o resumo daquele lote. Não capture erro de banco como se fosse rejeição de um candle.
- Total = inseridos + atualizados + ignorados + rejeitados.
- Exiba também índice e motivo de cada registro ignorado/rejeitado, sem expor stack trace para erros esperados.
- Saída 0 quando não houver rejeições, inclusive quando tudo for ignorado; 2 quando o lote terminar com registros rejeitados; 1 para falha de arquivo, estrutura ou banco. Falhas devem ser verificáveis por código de saída.
- O resumo persistido de uma nova tentativa é uma nova importação; idempotência refere-se ao estado dos candles, não à quantidade de resumos de execução.

CONSULTA E LACUNAS

Implemente consulta de candles por source, symbol, interval e período [início, fim), filtrado pelo open_time. Retorne em ordem cronológica. Inclua opção para consultar somente fechados.

Para detecção de lacunas, exija início e fim explícitos alinhados ao minuto. Gere as aberturas esperadas no intervalo e compare com os registros armazenados. Isso permite detectar lacunas internas e nas extremidades. Um candle aberto presente não é lacuna de presença; informe separadamente seu estado.

Não preencha lacunas com candles inventados. Recuperação nesta sprint significa importar outro arquivo fictício contendo o minuto ausente. Não calcule lacunas misturando pares ou origens.

CENÁRIOS E FIXTURES OBRIGATÓRIOS

Crie arquivos JSON pequenos em data/exemplos. Use 2026-11-05 e UTC.

A. Importação inicial
   Arquivo inicial.json com três candles de 1m, propositalmente fora de ordem: aberturas 12:03, 12:00 e 12:01.
   12:00 e 12:01 fechados; 12:03 aberto, snapshot às 12:03:30.
   Use no candle 12:00 exatamente o OHLCV do contrato de exemplo.
   Defina valores válidos e documentados para os outros dois.
   Resultado: 3 inseridos, 0 atualizados, 0 ignorados e 0 rejeitados. Consulta retorna 12:00, 12:01, 12:03.

B. Reimportação idempotente
   Reimporte inicial.json.
   Resultado: 0 inseridos, 0 atualizados, 3 ignorados, 0 rejeitados; continue com três candles e mesmos campos received_at.
   Teste também representação decimal equivalente com número diferente de zeros finais.

C. Atualização e fechamento
   Arquivo atualizacao.json com dois snapshots da chave 12:03, nesta ordem: um aberto às 12:03:50 e outro fechado às 12:04:00.
   Preserve open, faça high/volume não decrescentes e low não crescente; escolha valores explícitos verificáveis.
   Resultado na base após A/B: 0 inseridos, 2 atualizados, 0 ignorados, 0 rejeitados; continuam três candles, agora todos fechados.

D. Rejeições e obsolescência
   Crie fixtures e testes independentes para OHLC inconsistente, decimal inválido, volume negativo, data sem fuso, intervalo errado, snapshot obsoleto, mesmo snapshot com conteúdo divergente e alteração/reabertura de candle fechado.
   Para testar snapshot obsoleto, parta de um candle ainda aberto. Não execute esse caso somente depois do fechamento.
   Demonstre também um lote misto com um registro válido novo e um inválido: somente o válido é persistido, o resumo tem contagens corretas e a saída é 2.

E. Lacuna e recuperação
   Na base de A, para [12:00, 12:04), falta somente a abertura 12:02.
   Importe recuperacao.json com o candle 12:02 fechado: 1 inserido e demais contagens zero.
   Repita a consulta de lacunas: nenhuma ausência e quatro candles no total.
   Teste ainda base vazia e lacunas no início/fim do período.

COMANDOS

Implemente e documente pelo menos:

python -m candlevault importar --arquivo data/exemplos/inicial.json --banco data/candles.sqlite
python -m candlevault consultar --banco data/candles.sqlite --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
python -m candlevault lacunas --banco data/candles.sqlite --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
python -m candlevault demonstrar
python -m candlevault --help
python -m unittest discover -s tests -v

O comando demonstrar deve usar banco temporário novo, executar os cenários em sequência controlada, isolar os casos de erro e obsolescência e explicar os resultados sem alterar o banco do usuário. Deve funcionar novamente com os mesmos resultados lógicos. Horários do recebimento devem ser fixos nesse comando.

Comandos de consulta não devem criar silenciosamente um banco ausente; informe erro. A importação pode criar banco e diretório pai. Nenhum comando deve apagar banco existente. Execute a partir da raiz do projeto, sem instalar dependências; documente alternativa python3.

ENTREGÁVEIS

- pyproject.toml com metadados e Python mínimo.
- Pacote candlevault, fixtures JSON e testes unittest.
- README.md com comandos, contrato JSON, schema, fórmulas de validação, política de atualização e limites.
- docs/sprint03-glossario.md com ingestão, OHLCV, snapshot, UTC, chave composta, idempotência, transação, rollback, upsert, Decimal e lacuna.
- docs/sprint03-validacao.md com procedimento completo, consultas SQL de inspeção, contagens esperadas, resultados realmente observados e limitações.
- .gitignore para bancos de execução, arquivos auxiliares do SQLite, caches e ambientes virtuais, sem ignorar fixtures ou testes.

VALIDAÇÃO E ACEITE

Teste precisão decimal no ciclo JSON → domínio → SQLite → domínio, duplicação entre lotes e dentro do lote, atualização cumulativa válida/inválida, proteção de fechado, conflito temporal, normalização de fuso, limites de período, ordem cronológica, lacunas, contagens e códigos de saída.

Teste rollback técnico induzindo falha de gravação após uma primeira alteração dentro da transação: nem candles nem resumo desse lote devem permanecer gravados. Use banco temporário por teste e faça ao menos um teste com arquivo SQLite reaberto para demonstrar persistência.

Execute demonstrar, a sequência manual A/B/C/E, os casos inválidos, ajuda e testes. Não apresente dados esperados como evidência de execução real. Corrija falhas antes de concluir; registre explicitamente o que não pôde executar e por quê.

Finalize informando arquivos criados, comandos executados, resultados e simplificações. Não faça commits, publicação ou integração externa sem solicitação.
````

## 4. Conclusão da etapa

A etapa estará concluída quando o exemplo importar e consultar candles preservando precisão, impedir duplicações, controlar atualizações e identificar ausências sem inventar dados.

A próxima etapa será a definição de uma estratégia simples com regras objetivas de entrada e saída.
