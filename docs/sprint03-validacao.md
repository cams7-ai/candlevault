# Validação — Sprint 03

Execução realizada em 2026-11-05, com Python 3.12.14 e SQLite da biblioteca padrão.
Todos os comandos partiram da raiz do repositório, sem instalar dependências.
Foram usados bancos temporários novos, descartados ao final; nenhum banco do
usuário foi alterado. Os resultados abaixo foram observados em execução real.

## Reprodução manual A/B/C/E

Escolha um caminho **novo** para não misturar os resultados com importações antigas.
No shell Bash, a sequência abaixo cria um diretório temporário; não apaga bancos:

```bash
validacao_dir=$(mktemp -d)
validacao_banco="$validacao_dir/candles.sqlite"
python3 -m candlevault importar --arquivo data/exemplos/inicial.json --banco "$validacao_banco"
python3 -m candlevault consultar --banco "$validacao_banco" --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
python3 -m candlevault importar --arquivo data/exemplos/inicial.json --banco "$validacao_banco"
python3 -m candlevault lacunas --banco "$validacao_banco" --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
python3 -m candlevault importar --arquivo data/exemplos/atualizacao.json --banco "$validacao_banco"
python3 -m candlevault consultar --banco "$validacao_banco" --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00 --somente-fechados
python3 -m candlevault importar --arquivo data/exemplos/recuperacao.json --banco "$validacao_banco"
python3 -m candlevault lacunas --banco "$validacao_banco" --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
python3 -m candlevault consultar --banco "$validacao_banco" --origem FICTICIA --par BTCUSDT --intervalo 1m --inicio 2026-11-05T12:00:00+00:00 --fim 2026-11-05T12:04:00+00:00
```

Contagens na ordem `(inseridos, atualizados, ignorados, rejeitados)`:

| Etapa | Esperado pelo roteiro | Observado | Saída real |
| --- | --- | --- | --- |
| A / inicial | (3, 0, 0, 0) | (3, 0, 0, 0) | 0 |
| B / repetição | (0, 0, 3, 0) | (0, 0, 3, 0) | 0 |
| C / atualização e fechamento | (0, 2, 0, 0) | (0, 2, 0, 0) | 0 |
| E / recuperação | (1, 0, 0, 0) | (1, 0, 0, 0) | 0 |

A consulta inicial retornou 12:00, 12:01 e 12:03, nessa ordem, com dois fechados.
Antes da recuperação, `ausentes` continha somente
`2026-11-05T12:02:00.000000+00:00` e `abertos` continha 12:03.
Após C, a consulta de somente fechados retornou três candles. Após E, ambas as
listas de lacunas/abertos estavam vazias, e a consulta retornou quatro candles
fechados em ordem 12:00, 12:01, 12:02 e 12:03.

Inspeção SQL real após A/B/C/E: quatro candles e quatro resumos; linhas de resumo
na ordem `(total, inseridos, atualizados, ignorados, rejeitados)`:

```text
(3, 3, 0, 0, 0)
(3, 0, 0, 3, 0)
(2, 0, 2, 0, 0)
(1, 1, 0, 0, 0)
```

## Casos independentes D

Para cada linha, crie outro banco novo, importe `inicial.json` e então a fixture
indicada. Em particular, `obsoleto.json` deve ser executado enquanto 12:03 ainda
está aberto, antes de `atualizacao.json`.

```bash
caso_dir=$(mktemp -d)
python3 -m candlevault importar --arquivo data/exemplos/inicial.json --banco "$caso_dir/caso.sqlite"
python3 -m candlevault importar --arquivo data/exemplos/obsoleto.json --banco "$caso_dir/caso.sqlite"
echo $?
```

Troque `obsoleto.json` por cada fixture da tabela, usando um banco novo a cada caso.
Todos os casos foram executados como subprocessos do CLI; esperado e observado
coincidiram:

| Fixture | Esperado | Observado (I/A/G/R) | Saída real |
| --- | --- | --- | --- |
| ohlc_inconsistente.json | rejeitar | 0/0/0/1 | 2 |
| decimal_invalido.json | rejeitar | 0/0/0/1 | 2 |
| volume_negativo.json | rejeitar | 0/0/0/1 | 2 |
| data_sem_fuso.json | rejeitar | 0/0/0/1 | 2 |
| intervalo_errado.json | rejeitar | 0/0/0/1 | 2 |
| obsoleto.json | ignorar | 0/0/1/0 | 0 |
| conflito_snapshot.json | rejeitar | 0/0/0/1 | 2 |
| alteracao_fechado.json | rejeitar | 0/0/0/1 | 2 |
| reabertura_fechado.json | rejeitar | 0/0/0/1 | 2 |
| misto.json | aceitar só o válido | 1/0/0/1 | 2 |

No lote misto, somente 12:02 é inserido; o registro inválido não altera o candle
12:00. O teste também executa esse lote em base vazia e confirma um único candle
persistido e resumo `(2,1,0,0,1)`.

## Demonstração, ajuda e testes

Comandos executados:

```bash
python3 -m candlevault demonstrar
python3 -m candlevault --help
python3 -m unittest discover -s tests -v
```

A demonstração saiu com 0 e terminou A/B/C/E com quatro candles. Os casos D foram
isolados em bancos próprios. O teste de repetibilidade executou a demonstração duas
vezes e comparou a saída completa: idêntica. A ajuda saiu com 0.

Resultado da suíte: **18 testes passaram**. A suíte cobre:

- Precisão no ciclo arquivo JSON → Decimal → TEXT no SQLite → Decimal, inclusive
  valores com mais de 28 dígitos e volume muito pequeno; zeros finais equivalentes.
- Duplicatas entre lotes e dentro do lote, contagens, índice/motivo e preservação
  de `received_at` quando ignorado.
- Evolução cumulativa, fechamento, tentativa de reabertura, proteção de fechado,
  obsolescência, conflito no mesmo snapshot e atualização sem mudança OHLCV.
- Campos ausentes/adicionais, tipos inválidos, não finitos, OHLC, volume, booleanos,
  intervalo, alinhamento, duração, snapshot e identificadores.
- Fuso -03:00 normalizado para UTC, ordenação e limites semiabertos da consulta,
  filtro de fechados e isolamento de origem/par.
- Lacunas em base vazia, nas extremidades e internas; aberto presente é informado
  separadamente, sem preencher dados fictícios automaticamente.
- Envelope inválido, chaves duplicadas (inclusive aninhadas), constantes JSON
  não padrão, Unicode inválido e arquivo ausente, preservando o estado anterior.
- Falha técnica real por trigger SQLite na segunda gravação, após a primeira
  alteração no lote: rollback de todas as alterações desse lote, preservando lote
  anterior e seu resumo. Outro trigger faz falhar a escrita do resumo e confirma
  rollback dos candles. Não são capturadas como rejeição de registro.
- Banco em arquivo reaberto por outra conexão, confirmando persistência.
- CLI em subprocessos com saídas reais 0/1/2, consulta ausente sem criar banco,
  erros esperados sem stack trace e criação automática de diretórios na importação.

## Consultas SQL de inspeção

Use um cliente SQLite ou `sqlite3` da biblioteca padrão Python. O executável externo
`sqlite3` não é uma dependência. Exemplos de SQL (as datas devem ser canônicas):

```sql
SELECT source, symbol, interval, open_time, close_time,
       open, high, low, close, volume, is_closed, snapshot_at, received_at
FROM candles
WHERE source = 'FICTICIA' AND symbol = 'BTCUSDT' AND interval = '1m'
  AND open_time >= '2026-11-05T12:00:00.000000+00:00'
  AND open_time <  '2026-11-05T12:04:00.000000+00:00'
ORDER BY open_time;

SELECT id, filename, total, inseridos, atualizados, ignorados, rejeitados
FROM imports ORDER BY id;

SELECT count(*) AS quantidade FROM candles;
SELECT typeof(open), typeof(volume), typeof(is_closed) FROM candles LIMIT 1;
PRAGMA table_info(candles);
```

OHLCV devem ter tipo `text`, estado `integer`. Não faça cálculos financeiros,
conversão para REAL ou comparação numérica de preços em SQL textual. Reconstrua
`Decimal` em Python. Datas UTC canônicas podem ser comparadas textualmente.

## Limitações e simplificações

Não houve etapa de validação exigida que tenha ficado sem execução. O ambiente
validado foi Python 3.12.14; não foi executada matriz com outras versões de Python
ou sistemas operacionais. O código declara Python mínimo 3.11.

A sprint é local e didática: somente 1m, arquivos e lacunas em memória, sem migração
de banco anterior, histórico de snapshots, validação de fonte real ou integração
com mercado. O banco preserva apenas a versão atual e resumos. Não há arredondamento
financeiro nem cálculo de indicadores. Detalhes das rejeições são exibidos no CLI;
o resumo persistido armazena as contagens. A criação inicial das tabelas fica fora
da transação do lote, podendo restar schema vazio após uma falha técnica inicial.
