# Glossário — Sprint 03

| Termo | Significado neste laboratório |
| --- | --- |
| Candle | Agregação de preços e volume em um intervalo; não representa uma única execução. |
| Trade | Negócio executado, com preço e quantidade próprios. Não é importado aqui. |
| Bid/ask | Melhor oferta de compra/venda disponível; ofertas não são negócios executados. |
| Livro de ofertas | Conjunto de ordens de compra/venda ainda disponíveis, organizado por preço. Não é um conjunto de candles. |
| Ingestão | Leitura, conversão, validação e persistência dos registros recebidos. |
| OHLCV | Open (primeiro preço), high (máximo), low (mínimo), close (último) e volume do período. Nos exemplos, volume é BTC negociado. |
| Snapshot | Versão observada pela fonte em `snapshot_at`; um candle aberto pode ter vários snapshots cumulativos. |
| UTC | Referência temporal comum para normalizar fusos; persistida com offset +00:00. |
| Intervalo semiaberto | `[início, fim)` inclui início e exclui fim. Um candle de 12:00 vai até 12:01 exclusivo. |
| Recebimento | Instante local `received_at`, gerado pelo relógio da ingestão quando uma escrita é aceita. |
| Chave composta | Identidade formada por source, symbol, interval e open_time. |
| Idempotência | Repetir dados equivalentes mantém o mesmo estado dos candles; resumos das tentativas continuam sendo registrados. |
| Transação | Unidade atômica de gravação das alterações aceitas e do resumo de uma importação. |
| Rollback | Desfaz a transação inteira se ocorrer falha técnica; não desfaz lotes anteriores já confirmados. |
| Upsert | Inserir ou atualizar em caso de chave existente. O SQL usa essa operação somente após a política decidir que a escrita é permitida. |
| Decimal | Representação decimal exata criada a partir de string, evitando a conversão por ponto flutuante binário. Operações aritméticas ainda exigiriam escolher precisão/arredondamento adequados. |
| Lacuna | Abertura de minuto esperada, mas ausente na seleção de origem/par/intervalo e período. Um candle aberto presente não é ausência. |
| Obsoleto | Snapshot anterior ao armazenado de um candle ainda aberto; ignorado após validação. |
| Conflito | Conteúdo divergente no mesmo snapshot ou alteração proibida de um fechado; rejeitado sem sobrescrever. |
| Candle fechado | Versão cuja janela terminou segundo a convenção da fonte fictícia; protegida contra alterações neste laboratório. |
