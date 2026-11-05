"""Consultas por período e lacunas de presença."""
from .domain import MINUTE, ValidationError, canonical, selection


def validate_period(source, symbol, interval, start, end, *, aligned=False):
    selection(source, symbol, interval)
    if start >= end:
        raise ValidationError('início deve ser anterior ao fim')
    if aligned and any(t.second or t.microsecond for t in (start, end)):
        raise ValidationError('limites de lacunas devem estar alinhados ao minuto')


def gaps(repo, source, symbol, interval, start, end):
    validate_period(source, symbol, interval, start, end, aligned=True)
    rows = repo.query(source, symbol, interval, start, end)
    present = {c.open_time for c in rows}
    missing = []
    cursor = start
    while cursor < end:
        if cursor not in present:
            missing.append(canonical(cursor))
        cursor += MINUTE
    return {'ausentes': missing,
            'abertos': [canonical(c.open_time) for c in rows if not c.is_closed]}
