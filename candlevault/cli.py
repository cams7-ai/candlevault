"""Interface de terminal; saída JSON para inspeção e automação."""
import argparse
from datetime import datetime, timezone
import json
import sqlite3
import sys

from .domain import ValidationError, timestamp
from .ingestion import ingest
from .queries import gaps, validate_period
from .reader import FileError, read_file
from .repository import connect


def parser():
    cli = argparse.ArgumentParser(description='CandleVault: candles fictícios JSON → SQLite')
    commands = cli.add_subparsers(dest='command', required=True)
    imp = commands.add_parser('importar', help='Importar lote JSON')
    imp.add_argument('--arquivo', required=True)
    imp.add_argument('--banco', required=True)
    for name in ('consultar', 'lacunas'):
        cmd = commands.add_parser(name, help=f'{name.capitalize()} por período [início, fim)')
        for option in ('banco', 'origem', 'par', 'intervalo', 'inicio', 'fim'):
            cmd.add_argument('--' + option, required=True)
        if name == 'consultar':
            cmd.add_argument('--somente-fechados', action='store_true')
    commands.add_parser('demonstrar', help='Executar cenários em bancos temporários')
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'demonstrar':
            from .demo import demonstrate
            demonstrate()
            return 0
        if args.command == 'importar':
            records = read_file(args.arquivo)
            with connect(args.banco, create=True) as repo:
                report = ingest(repo, records, args.arquivo, lambda: datetime.now(timezone.utc))
            print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
            return report.exit_code
        start, end = timestamp(args.inicio), timestamp(args.fim)
        validate_period(args.origem, args.par, args.intervalo, start, end,
                        aligned=args.command == 'lacunas')
        with connect(args.banco) as repo:
            if args.command == 'lacunas':
                result = gaps(repo, args.origem, args.par, args.intervalo, start, end)
            else:
                result = [c.as_dict() for c in repo.query(args.origem, args.par, args.intervalo,
                                                         start, end, args.somente_fechados)]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (FileError, ValidationError, sqlite3.Error, OSError) as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        return 1
