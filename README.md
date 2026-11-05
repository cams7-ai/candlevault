# CandleVault — Sprint 03

Laboratório didático de coleta e armazenamento de candles fictícios. Python 3.11+
com biblioteca padrão, sem instalação de dependências, rede ou credenciais.
Execute os comandos a partir da raiz deste repositório. Se `python` não estiver
disponível, substitua por `python3` (usado na validação desta entrega).

## Executar

```bash
python -m candlevault --help
python -m candlevault importar --arquivo data/exemplos/inicial.json --banco data/candles.sqlite
python -m candlevault consultar --banco data/candles.sqlite --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
python -m candlevault lacunas --banco data/candles.sqlite --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
python -m candlevault demonstrar
python -m unittest discover -s tests -v
```

Acrescente `--somente-fechados` a `consultar` para filtrar candles fechados.
Consulta e lacunas abrem o SQLite em modo somente leitura: banco ausente é erro,
sem criação silenciosa. Importar cria o banco, schema e diretórios pais, se preciso.
Nenhum comando apaga um banco existente. A demonstração usa bancos temporários,
relógio fixo em `2026-11-05T13:00:00+00:00` e casos de erro independentes.

As saídas são JSON, exceto a demonstração explicativa. Cada registro de importação
recebe uma classificação; ignorados/rejeitados incluem motivo e índice **a partir de
zero** na lista original. O total é a soma das quatro contagens.

| Código de saída | Significado |
| --- | --- |
| 0 | Lote sem rejeições (inclusive vazio ou só ignorados), consulta ou demonstração concluída |
| 2 | Lote concluído com registros rejeitados |
| 1 | Falha de arquivo, estrutura, banco ou parâmetros de domínio |

O `argparse` também retorna 2 para sintaxe de comando inválida, com ajuda em stderr.
Erros esperados aparecem sem stack trace. Use `echo $?` logo após um comando para
verificar seu código de saída no shell.

## Contrato JSON e validação

Envelope com **exatamente** `schema_version` (inteiro 1; booleano não vale) e
`candles` (lista). Cada item exige exatamente estes campos:

```json
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
```

- `source` e `symbol`: conjunto `[A-Z][A-Z0-9_]*` (ASCII), sem normalização.
  Outras origens e pares nesse conjunto são aceitos para testar isolamento.
  Os exemplos usam FICTICIA/BTCUSDT e volume do ativo base em BTC.
- `interval`: somente `1m`. `is_closed`: booleano JSON real.
- OHLCV: strings no formato `-?[0-9]+\.[0-9]+`, convertidas diretamente em
  `Decimal`. Ponto e casas decimais são obrigatórios; expoentes, espaços, vírgulas,
  números JSON, NaN, sNaN e infinitos são rejeitados. Não há uso de `float`.
- Preços > 0, volume >= 0; `low <= high`, `low <= open <= high` e
  `low <= close <= high`.
- Horários: ISO 8601 aceito por `datetime.fromisoformat`, sempre com fuso explícito,
  normalizado para UTC. Abertura com segundo e microssegundo zero.
  `close_time - open_time = 1 minuto`.
- `close_time` é o fim **exclusivo** de `[open_time, close_time)`. É uma convenção
  local; não corresponde automaticamente ao contrato de uma API externa.
- `snapshot_at` é o instante em que a fonte fictícia observou a versão:
  aberto exige `open_time <= snapshot_at < close_time`; fechado exige
  `snapshot_at >= close_time`.
- `received_at` é gerado pelo relógio da aplicação apenas em inserções/atualizações
  aceitas. Não faz parte do JSON. Representa recebimento local, não abertura,
  fechamento ou observação pela fonte. O resumo recebe também seu horário local.

Arquivo ilegível, JSON malformado, chave duplicada em qualquer nível, constante
JSON não padrão ou envelope inválido rejeitam o arquivo inteiro antes de abrir o
banco. Um item inválido dentro de uma lista válida rejeita só aquele item; os
outros continuam. Um item que não seja objeto também é rejeitado individualmente.

## Política de atualização

A validação individual ocorre primeiro. Para registros válidos, esta é a precedência:

1. Chave inexistente: inserir.
2. Conteúdo de domínio e snapshot equivalentes: ignorar duplicação exata.
3. Existente fechado: conteúdo igual é ignorado mesmo com outro snapshot;
   qualquer alteração de domínio ou reabertura é conflito rejeitado.
4. Existente aberto com snapshot anterior: ignorar como obsoleto.
5. Mesmo snapshot com conteúdo divergente: rejeitar conflito.
6. Snapshot posterior de aberto: atualizar se mantiver `open`, não reduzir `high`,
   não aumentar `low` e não reduzir `volume`. `close` pode variar nos limites OHLC.
   Pode fechar o candle. Atualiza `snapshot_at` e `received_at` mesmo sem mudança OHLCV.

Conteúdo de domínio inclui identidade, início/fim, OHLCV e estado; exclui snapshot
e recebimento. Decimais são comparados numericamente: `100000.0 = 100000.00`.
Ignorar ou rejeitar preserva todos os campos existentes, inclusive `received_at`.
Mudança em `open_time` representa outra chave; duração inválida é rejeitada na
validação. Não se tenta inferir que outra chave seja correção de um candle anterior.

Pressupõem-se snapshots cumulativos sem correção da fonte. Não há correção automática
de fechado. A ordem do arquivo é preservada; duplicatas dentro do próprio lote
seguem a mesma política aplicada entre lotes.

## Persistência e transações

O schema completo está em `candlevault/repository.py`:

| Tabela | Campos |
| --- | --- |
| `candles` | source, symbol, interval, open_time, close_time, open, high, low, close, volume, is_closed, snapshot_at, received_at |
| `imports` | id, filename, received_at, total, inseridos, atualizados, ignorados, rejeitados |

Chave primária de candles: `(source, symbol, interval, open_time)`.
Datas são TEXT UTC de largura fixa, como `2026-11-05T12:00:00.000000+00:00`.
OHLCV são TEXT decimais; ao consultar, voltam a ser `Decimal`. Estado é INTEGER
0/1 com CHECK. Resumos têm CHECK da soma das contagens.

A ordenação textual das **datas canônicas** coincide com a cronológica. Isso não se
aplica a preços: não use ordenação/comparação textual, `REAL`, `CAST AS REAL` ou
agregações SQL para cálculos financeiros. Faça cálculos em Python com `Decimal` e
uma política explícita de precisão. A sprint preserva valores; não calcula indicadores.

Uma transação `BEGIN IMMEDIATE` cobre alterações aceitas e resumo de cada lote.
Falha técnica de gravação desfaz ambos e sai com 1; não é classificada como rejeição
de domínio. Rejeições de domínio não impedem a persistência dos registros válidos.
A criação inicial do schema ocorre antes dessa transação; um banco novo pode ficar
com tabelas vazias após uma falha técnica. Conexões são sempre fechadas.

Reimportar gera outro resumo, mesmo sem modificar candles. Só o estado dos candles
é idempotente. Guarda-se a versão atual; não o arquivo bruto nem todas as versões.

## Consultas, exemplos e recuperação

`consultar` filtra por origem/par/intervalo e `open_time` no período `[início, fim)`,
sempre ordenado. `lacunas` exige limites explícitos alinhados ao minuto e compara
as aberturas esperadas com as presentes; inclui faltas nas extremidades e base vazia.
Candles abertos presentes são listados em `abertos`, sem serem contados como lacuna.
Não se inventam candles nem se misturam origens ou pares.

Valores dos exemplos (todos em 2026-11-05 UTC):

| Arquivo / abertura | Open | High | Low | Close | Volume BTC | Snapshot / estado |
| --- | --- | --- | --- | --- | --- | --- |
| inicial / 12:00 | 100000.00 | 100100.00 | 99900.00 | 100050.25 | 0.125 | 12:01:00 fechado |
| inicial / 12:01 | 100050.25 | 100200.00 | 100000.00 | 100150.00 | 0.250 | 12:02:00 fechado |
| inicial / 12:03 | 100150.00 | 100250.00 | 100100.00 | 100200.00 | 0.100 | 12:03:30 aberto |
| atualizacao / 12:03 | 100150.00 | 100300.00 | 100090.00 | 100280.00 | 0.180 | 12:03:50 aberto |
| atualizacao / 12:03 | 100150.00 | 100320.00 | 100080.00 | 100300.00 | 0.220 | 12:04:00 fechado |
| recuperacao / 12:02 | 100150.00 | 100220.00 | 100100.00 | 100150.00 | 0.175 | 12:03:00 fechado |

`inicial.json` está na ordem 12:03, 12:00, 12:01. Para recuperar a lacuna 12:02,
importe `recuperacao.json`. Fixtures adicionais cobrem rejeições, obsolescência,
conflito temporal, alteração/reabertura de fechado e lote misto.

## Organização e limites

- `reader.py`: envelope JSON estrito; `domain.py`: tipos, precisão e validação.
- `policy.py`: precedência das regras; `repository.py`: SQL e transações.
- `ingestion.py`: processamento ordenado com relógio injetado, sem impressão.
- `queries.py`: períodos e lacunas; `cli.py` e `demo.py`: apresentação.
- `tests/test_candlevault.py`: testes com SQLite temporário e CLI em subprocessos.
- [Glossário](docs/sprint03-glossario.md) e [validação executada](docs/sprint03-validacao.md).

Simplificações: somente candles de 1m, arquivo inteiro em memória, SQLite local,
versão atual por chave e contagens por execução. Lacunas são enumeradas minuto a
minuto em memória; use períodos pequenos. Sem migração de schemas legados, histórico
de revisões, API, agendamento, estratégias, backtest, ordens ou integração externa.
