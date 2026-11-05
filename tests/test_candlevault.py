import contextlib
from datetime import timedelta
from decimal import Decimal
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from candlevault.demo import EXAMPLES, FIXED_TIME
from candlevault.domain import ValidationError, canonical, parse_candle, timestamp
from candlevault.ingestion import ingest, import_file
from candlevault.queries import gaps, validate_period
from candlevault.reader import FileError, read_file
from candlevault.repository import connect

START = timestamp('2026-11-05T12:00:00+00:00')
END = START + timedelta(minutes=4)


class CandleVaultTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'candles.sqlite'
        self.manager = connect(self.path, create=True)
        self.repo = self.manager.__enter__()
        self.addCleanup(self.manager.__exit__, None, None, None)
        self.initial = read_file(EXAMPLES / 'inicial.json')
        self.open = self.initial[0]
        self.closed = self.initial[1]
        self.clock = lambda: FIXED_TIME

    def ingest(self, records):
        return ingest(self.repo, records, 'teste.json', self.clock)

    def load(self, name):
        return import_file(self.repo, EXAMPLES / (name + '.json'), self.clock)

    def query(self, start=START, end=END, closed=False, source='FICTICIA', symbol='BTCUSDT'):
        return self.repo.query(source, symbol, '1m', start, end, closed)

    def gap(self, start=START, end=END, source='FICTICIA', symbol='BTCUSDT'):
        return gaps(self.repo, source, symbol, '1m', start, end)

    def test_sequence_persistence_and_summary(self):
        self.assertEqual(self.load('inicial').counts, dict(inseridos=3, atualizados=0, ignorados=0, rejeitados=0))
        received = [tuple(r) for r in self.repo.db.execute('SELECT open_time, received_at FROM candles ORDER BY open_time')]
        self.clock = lambda: FIXED_TIME + timedelta(hours=1)
        self.assertEqual(self.load('inicial').counts['ignorados'], 3)
        self.assertEqual(received, [tuple(r) for r in self.repo.db.execute('SELECT open_time, received_at FROM candles ORDER BY open_time')])
        self.assertEqual([c.open_time.minute for c in self.query()], [0, 1, 3])
        self.assertEqual(len(self.query(closed=True)), 2)
        self.assertEqual(self.gap(), {'ausentes': [canonical(START + timedelta(minutes=2))], 'abertos': [canonical(START + timedelta(minutes=3))]})
        self.assertEqual(self.load('atualizacao').counts['atualizados'], 2)
        self.assertEqual(len(self.query(closed=True)), 3)
        self.assertEqual(self.load('recuperacao').counts['inseridos'], 1)
        self.assertEqual(self.gap(), {'ausentes': [], 'abertos': []})
        with connect(self.path) as reopened:
            self.assertEqual(len(reopened.query('FICTICIA', 'BTCUSDT', '1m', START, END)), 4)
            self.assertEqual(reopened.db.execute('SELECT count(*) FROM imports').fetchone()[0], 4)
            self.assertEqual(reopened.db.execute('SELECT sum(total) FROM imports').fetchone()[0], 9)

    def test_decimal_round_trip_without_float_or_context_rounding(self):
        raw = dict(self.closed, open='100000.000000000000000000000000000000000001',
                   close='100000.000000000000000000000000000000000002',
                   volume='0.000000000000000000000000000000000000000001')
        json_path = Path(self.temp.name) / 'precisao.json'
        json_path.write_text(json.dumps({'schema_version': 1, 'candles': [raw]}))
        import_file(self.repo, json_path, self.clock)
        candle = self.query()[0]
        self.assertEqual(candle.open, Decimal(raw['open']))
        self.assertEqual(candle.close, Decimal(raw['close']))
        self.assertEqual(candle.volume, Decimal(raw['volume']))
        self.assertEqual(self.repo.db.execute('SELECT typeof(open), typeof(volume) FROM candles').fetchone()[:], ('text', 'text'))
        self.assertEqual(self.ingest([dict(raw, open=raw['open']+'0')]).counts['ignorados'], 1)

    def test_duplicates_in_batch_and_between_batches(self):
        result = self.ingest([self.closed, dict(self.closed, open='100000.0'), self.closed])
        self.assertEqual(list(result.counts.values()), [1, 0, 2, 0])
        self.assertEqual([d['indice'] for d in result.details], [1, 2])
        self.assertEqual(self.ingest([self.closed]).counts['ignorados'], 1)

    def test_all_fixture_errors_independently(self):
        self.load('inicial')
        for name in ('ohlc_inconsistente', 'decimal_invalido', 'volume_negativo', 'data_sem_fuso',
                     'intervalo_errado', 'conflito_snapshot', 'alteracao_fechado', 'reabertura_fechado'):
            with self.subTest(name=name):
                result = self.load(name)
                self.assertEqual(result.counts['rejeitados'], 1)
                self.assertEqual(result.exit_code, 2)
                self.assertTrue(result.details[0]['motivo'])
        result = self.load('obsoleto')
        self.assertEqual(result.counts['ignorados'], 1)
        self.assertEqual(result.details[0]['motivo'], 'snapshot obsoleto')
        self.assertEqual(result.exit_code, 0)

    def test_cumulative_changes_rejected_and_later_unchanged_snapshot_accepted(self):
        self.ingest([self.open])
        for change in ({'open':'100151.00'}, {'high':'100240.00'},
                       {'low':'100110.00'}, {'volume':'0.090'}):
            with self.subTest(change=change):
                candidate = dict(self.open, snapshot_at='2026-11-05T12:03:40+00:00', **change)
                self.assertEqual(self.ingest([candidate]).counts['rejeitados'], 1)
        self.clock = lambda: FIXED_TIME + timedelta(seconds=10)
        candidate = dict(self.open, snapshot_at='2026-11-05T12:03:50+00:00')
        self.assertEqual(self.ingest([candidate]).counts['atualizados'], 1)
        row = self.repo.db.execute('SELECT snapshot_at, received_at FROM candles').fetchone()
        self.assertEqual(row['snapshot_at'], canonical(timestamp(candidate['snapshot_at'])))
        self.assertEqual(row['received_at'], canonical(self.clock()))

    def test_closed_protection_precedes_obsolete_and_equal_content_ignores_snapshot(self):
        self.ingest([self.closed])
        self.assertEqual(self.ingest([dict(self.closed, snapshot_at='2026-11-05T12:02:00+00:00')]).counts['ignorados'], 1)
        self.assertEqual(self.ingest([dict(self.closed, is_closed=False, snapshot_at='2026-11-05T12:00:10+00:00')]).counts['rejeitados'], 1)
        self.assertEqual(self.query()[0].snapshot_at, timestamp(self.closed['snapshot_at']))

    def test_obsolete_precedes_content_conflict_for_open(self):
        self.ingest([self.open])
        old = dict(self.open, open='100151.00', snapshot_at='2026-11-05T12:03:10+00:00')
        self.assertEqual(self.ingest([old]).counts['ignorados'], 1)

    def test_record_contract_and_invalid_fields(self):
        invalid = [None, [], 1, 'candle', {}, dict(self.closed, extra='x')]
        missing = dict(self.closed)
        del missing['close']
        invalid.append(missing)
        for field, values in {
            'open': ['', 'NaN', 'sNaN', 'Infinity', '-Infinity', '1,000.00', '1e5', '100000', ' 100000.00', 100000.0, '0.0', '-1.0'],
            'volume': ['-1.0'], 'is_closed': ['true', 1, None],
            'source': ['', ' FICTICIA', 'ficticia', 'X-Y', '1X', None],
            'symbol': ['', 'BTCUSDT ', 'btcusdt'],
            'interval': ['5m', None],
            'open_time': ['2026-11-05T12:00:01+00:00', '2026-11-05T12:00:00.000001+00:00', '2026-11-05T12:00:00', 'invalid', 1],
            'close_time': ['2026-11-05T12:02:00+00:00'],
            'snapshot_at': ['2026-11-05T11:59:00+00:00', '2026-11-05T12:00:30+00:00'],
            'low': ['100001.00'], 'close': ['100101.00'],
        }.items():
            invalid.extend(dict(self.closed, **{field:v}) for v in values)
        for raw in invalid:
            with self.subTest(raw=raw):
                with self.assertRaises(ValidationError):
                    parse_candle(raw)
        for snap in ('2026-11-05T12:02:59+00:00', '2026-11-05T12:04:00+00:00'):
            with self.assertRaises(ValidationError):
                parse_candle(dict(self.open, snapshot_at=snap))

    def test_timezone_normalization_and_zero_volume(self):
        offset = dict(self.closed, open_time='2026-11-05T09:00:00-03:00',
                      close_time='2026-11-05T09:01:00-03:00', snapshot_at='2026-11-05T09:01:00-03:00')
        result = self.ingest([self.closed, offset])
        self.assertEqual(list(result.counts.values()), [1, 0, 1, 0])
        row = self.repo.db.execute('SELECT open_time FROM candles').fetchone()[0]
        self.assertEqual(row, '2026-11-05T12:00:00.000000+00:00')
        self.assertEqual(parse_candle(dict(self.closed, volume='0.0')).volume, Decimal(0))

    def test_gaps_empty_edges_and_identity_isolation(self):
        self.assertEqual(len(self.gap()['ausentes']), 4)
        self.ingest([self.initial[2]])  # somente 12:01
        self.assertEqual(self.gap()['ausentes'], [canonical(START + timedelta(minutes=m)) for m in (0, 2, 3)])
        self.ingest([dict(self.closed, source='OUTRA'), dict(self.open, symbol='ETHUSDT')])
        self.assertEqual(len(self.gap()['ausentes']), 3)
        self.assertEqual(len(self.query(source='OUTRA')), 1)
        self.assertEqual(len(self.query(symbol='ETHUSDT')), 1)
        self.assertEqual(self.gap(source='OUTRA')['ausentes'][0], canonical(START + timedelta(minutes=1)))

    def test_half_open_period_and_alignment(self):
        self.load('inicial')
        self.assertEqual([c.open_time.minute for c in self.query(START, START + timedelta(minutes=1))], [0])
        self.assertEqual([c.open_time.minute for c in self.query(START+timedelta(seconds=1), END)], [1,3])
        for start, end in ((END, START), (START, START), (START+timedelta(seconds=1), END)):
            with self.assertRaises(ValidationError):
                self.gap(start, end)
        with self.assertRaises(ValidationError):
            validate_period('FICTICIA', 'BTCUSDT', '5m', START, END)

    def test_mixed_batch_summary_and_no_partial_invalid_record(self):
        result = self.load('misto')
        self.assertEqual(list(result.counts.values()), [1, 0, 0, 1])
        self.assertEqual(result.exit_code, 2)
        self.assertEqual(len(self.query()), 1)
        row = dict(self.repo.db.execute('SELECT * FROM imports').fetchone())
        self.assertEqual([row[k] for k in ('total','inseridos','atualizados','ignorados','rejeitados')], [2,1,0,0,1])

    def test_technical_rollback_after_first_write_preserves_previous_batch(self):
        self.ingest([self.open])
        # 12:00 será escrito; a segunda escrita (12:01) falha realmente no SQLite.
        self.repo.db.execute("""CREATE TRIGGER fail_second BEFORE INSERT ON candles
            WHEN NEW.open_time = '2026-11-05T12:01:00.000000+00:00'
            BEGIN SELECT RAISE(ABORT, 'falha técnica induzida'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.ingest([self.closed, self.initial[2]])
        self.assertEqual([c.open_time.minute for c in self.query()], [3])
        self.assertEqual(self.repo.db.execute('SELECT count(*) FROM imports').fetchone()[0], 1)
        with connect(self.path) as reopened:
            self.assertEqual(reopened.db.execute('SELECT count(*) FROM candles').fetchone()[0], 1)

    def test_summary_write_failure_rolls_back_candles(self):
        self.repo.db.execute("""CREATE TRIGGER fail_summary BEFORE INSERT ON imports
            BEGIN SELECT RAISE(ABORT, 'resumo indisponível'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.ingest([self.closed])
        self.assertEqual(len(self.query()), 0)
        self.assertEqual(self.repo.db.execute('SELECT count(*) FROM imports').fetchone()[0], 0)

    def test_envelope_failures_leave_database_unchanged(self):
        self.load('inicial')
        invalid = ['{', '[]', '{}', '{"schema_version":true,"candles":[]}',
                   '{"schema_version":2,"candles":[]}', '{"schema_version":1,"candles":{}}',
                   '{"schema_version":1,"schema_version":1,"candles":[]}',
                   '{"schema_version":1,"candles":[{"x":1,"x":2}]}',
                   '{"schema_version":1,"candles":[NaN]}',
                   '{"schema_version":1,"candles":[Infinity]}',
                   '{"schema_version":1,"candles":[-Infinity]}']
        path = Path(self.temp.name) / 'invalid.json'
        for content in invalid:
            with self.subTest(content=content):
                path.write_text(content)
                with self.assertRaises(FileError):
                    import_file(self.repo, path, self.clock)
        path.write_bytes(b'\xff')
        with self.assertRaises(FileError):
            read_file(path)
        with self.assertRaises(FileError):
            read_file(Path(self.temp.name) / 'missing.json')
        self.assertEqual(len(self.query()), 3)
        self.assertEqual(self.repo.db.execute('SELECT count(*) FROM imports').fetchone()[0], 1)

    def test_empty_batch_persists_zero_summary(self):
        result = self.ingest([])
        self.assertEqual(result.as_dict()['total'], 0)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(self.repo.db.execute('SELECT total FROM imports').fetchone()[0], 0)

    def test_cli_actual_exit_codes_missing_db_and_json_output(self):
        def run(*args):
            return subprocess.run([sys.executable, '-m', 'candlevault', *map(str, args)], capture_output=True, text=True)
        path = Path(self.temp.name) / 'cli' / 'new.sqlite'
        initial = run('importar', '--arquivo', EXAMPLES / 'inicial.json', '--banco', path)
        self.assertEqual(initial.returncode, 0, initial.stderr)
        self.assertEqual(json.loads(initial.stdout)['inseridos'], 3)
        repeated = run('importar', '--arquivo', EXAMPLES / 'inicial.json', '--banco', path)
        self.assertEqual(repeated.returncode, 0)
        self.assertEqual(json.loads(repeated.stdout)['ignorados'], 3)
        mixed = run('importar', '--arquivo', EXAMPLES / 'misto.json', '--banco', path)
        self.assertEqual(mixed.returncode, 2)
        self.assertEqual(json.loads(mixed.stdout)['rejeitados'], 1)
        options = ['--origem','FICTICIA','--par','BTCUSDT','--intervalo','1m',
                   '--inicio',canonical(START),'--fim',canonical(END)]
        result = run('consultar', '--banco', path, *options, '--somente-fechados')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(json.loads(result.stdout)), 3)
        missing = Path(self.temp.name) / 'absent.sqlite'
        for command in ('consultar', 'lacunas'):
            failure = run(command, '--banco', missing, *options)
            self.assertEqual(failure.returncode, 1)
            self.assertNotIn('Traceback', failure.stderr)
            self.assertFalse(missing.exists())
        failure = run('importar', '--arquivo', missing, '--banco', missing)
        self.assertEqual(failure.returncode, 1)
        self.assertFalse(missing.exists())
        self.assertEqual(run('--help').returncode, 0)
        self.assertEqual(run('importar','--arquivo', EXAMPLES/'inicial.json','--banco', self.temp.name).returncode, 1)

    def test_demo_is_repeatable(self):
        from candlevault.demo import demonstrate
        outputs = []
        for _ in range(2):
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                demonstrate()
            outputs.append(stream.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn('Total persistido: 4', outputs[0])


if __name__ == '__main__':
    unittest.main()
