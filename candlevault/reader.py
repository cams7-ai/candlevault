"""Leitura estrita do envelope JSON antes de abrir o banco."""
import json
from pathlib import Path


class FileError(ValueError):
    """Falha no arquivo ou no envelope da importação."""


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise FileError(f'chave JSON duplicada: {key}')
        result[key] = value
    return result


def invalid_constant(value: str):
    raise FileError(f'constante JSON não permitida: {value}')


def read_file(path: str | Path) -> list:
    try:
        with Path(path).open(encoding='utf-8') as stream:
            data = json.load(stream, object_pairs_hook=unique_object,
                             parse_constant=invalid_constant)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise FileError(f'falha ao ler JSON: {exc}') from exc
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'candles'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or not isinstance(data['candles'], list)):
        raise FileError('envelope exige schema_version inteiro 1 e candles como lista')
    return data['candles']
