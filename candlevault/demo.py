"""Roteiro reproduzível; nunca acessa banco do usuário."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .domain import timestamp
from .ingestion import import_file
from .queries import gaps
from .repository import connect

EXAMPLES = Path(__file__).resolve().parent.parent / 'data' / 'exemplos'
FIXED_TIME = timestamp('2026-11-05T13:00:00+00:00')


def demonstrate():
    def run(repo, name, label):
        result = import_file(repo, EXAMPLES / (name + '.json'), lambda: FIXED_TIME)
        print(f'{label}: {json.dumps(result.as_dict(), ensure_ascii=False)}; saída={result.exit_code}')
        return result

    def show_gaps(repo, label):
        result = gaps(repo, 'FICTICIA', 'BTCUSDT', '1m',
                      timestamp('2026-11-05T12:00:00+00:00'),
                      timestamp('2026-11-05T12:04:00+00:00'))
        print(f'{label}: {json.dumps(result, ensure_ascii=False)}')

    with TemporaryDirectory(prefix='candlevault-demo-') as directory:
        with connect(Path(directory) / 'sequencia.sqlite', create=True) as repo:
            run(repo, 'inicial', 'A — três inserções, incluindo um candle aberto')
            run(repo, 'inicial', 'B — reimportação idempotente')
            show_gaps(repo, 'E — lacuna de presença em 12:02; aberto em 12:03')
            run(repo, 'atualizacao', 'C — atualização e fechamento de 12:03')
            run(repo, 'recuperacao', 'E — recuperação por arquivo fictício')
            show_gaps(repo, 'E — sem lacunas e sem candles abertos')
            print(f"Total persistido: {repo.db.execute('SELECT count(*) FROM candles').fetchone()[0]}")
        for name in ('ohlc_inconsistente', 'decimal_invalido', 'volume_negativo', 'data_sem_fuso',
                     'intervalo_errado', 'obsoleto', 'conflito_snapshot', 'alteracao_fechado',
                     'reabertura_fechado', 'misto'):
            with connect(Path(directory) / (name + '.sqlite'), create=True) as repo:
                import_file(repo, EXAMPLES / 'inicial.json', lambda: FIXED_TIME)
                run(repo, name, f'D — caso independente {name}')
