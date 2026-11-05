"""Contrato e validação do domínio, sem efeitos de entrada/saída."""
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import re


class ValidationError(ValueError):
    """Um registro não atende ao contrato."""


MINUTE = timedelta(minutes=1)
DECIMALS = ('open', 'high', 'low', 'close', 'volume')
TIMES = ('open_time', 'close_time', 'snapshot_at')


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError('data deve ser string ISO 8601 com fuso')
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError('fuso ausente')
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValidationError(f'data inválida: {value}') from exc


def canonical(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValidationError('relógio deve fornecer data com fuso')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')


def identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]*', value):
        raise ValidationError(f'{name}: use letras maiúsculas ASCII, dígitos ou _, iniciando por letra')
    return value


def selection(source: str, symbol: str, interval: str) -> None:
    identifier(source, 'source')
    identifier(symbol, 'symbol')
    if interval != '1m':
        raise ValidationError('interval deve ser 1m')


@dataclass(frozen=True)
class Candle:
    source: str
    symbol: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    is_closed: bool
    snapshot_at: datetime

    @property
    def key(self) -> tuple:
        return self.source, self.symbol, self.interval, canonical(self.open_time)

    def same_domain(self, other: 'Candle') -> bool:
        return all(getattr(self, f.name) == getattr(other, f.name)
                   for f in fields(self) if f.name != 'snapshot_at')

    def as_dict(self) -> dict:
        return {f.name: canonical(v) if isinstance(v, datetime)
                else format(v, 'f') if isinstance(v, Decimal) else v
                for f in fields(self) for v in [getattr(self, f.name)]}


def parse_candle(raw: object) -> Candle:
    expected = {f.name for f in fields(Candle)}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValidationError('candle deve conter exatamente os campos do contrato')
    data = dict(raw)
    selection(data['source'], data['symbol'], data['interval'])
    for name in DECIMALS:
        value = data[name]
        if not isinstance(value, str) or not re.fullmatch(r'-?[0-9]+\.[0-9]+', value):
            raise ValidationError(f'{name}: exige string decimal finita com ponto (ex.: 1.00)')
        data[name] = Decimal(value)
    if any(data[n] <= 0 for n in DECIMALS[:-1]) or data['volume'] < 0:
        raise ValidationError('preços devem ser positivos e volume não negativo')
    if not (data['low'] <= data['open'] <= data['high']
            and data['low'] <= data['close'] <= data['high']):
        raise ValidationError('OHLC inconsistente: low <= open/close <= high')
    if type(data['is_closed']) is not bool:
        raise ValidationError('is_closed deve ser booleano')
    for name in TIMES:
        data[name] = timestamp(data[name])
    start, end, snap = (data[n] for n in TIMES)
    if start.second or start.microsecond or end - start != MINUTE:
        raise ValidationError('abertura deve estar alinhada ao minuto e duração deve ser 1m')
    if snap < start or (data['is_closed'] and snap < end) or (not data['is_closed'] and snap >= end):
        raise ValidationError('snapshot_at incompatível com intervalo/estado do candle')
    return Candle(**data)
