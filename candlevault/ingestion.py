"""Ingestão ordenada e transacional com relógio injetado."""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .domain import ValidationError, canonical, parse_candle
from .policy import classify
from .reader import read_file
from .repository import Repository


@dataclass
class Report:
    counts: dict[str, int]
    details: list[dict]

    @property
    def exit_code(self) -> int:
        return 2 if self.counts['rejeitados'] else 0

    def as_dict(self) -> dict:
        return {'total': sum(self.counts.values()), **self.counts, 'detalhes': self.details}


def ingest(repo: Repository, records: list, filename: str, clock: Callable[[], datetime]) -> Report:
    counts = dict.fromkeys(('inseridos', 'atualizados', 'ignorados', 'rejeitados'), 0)
    details = []
    with repo.transaction():
        for index, raw in enumerate(records):
            # Somente falhas de domínio são classificadas como rejeição.
            try:
                candle = parse_candle(raw)
            except ValidationError as exc:
                status, reason = 'rejeitados', str(exc)
            else:
                status, reason = classify(repo.get(candle), candle)
                if status in ('inseridos', 'atualizados'):
                    repo.save(candle, canonical(clock()))
            counts[status] += 1
            if status in ('ignorados', 'rejeitados'):
                details.append({'indice': index, 'classificacao': status, 'motivo': reason})
        repo.summary(str(filename), canonical(clock()), counts)
    return Report(counts, details)


def import_file(repo: Repository, filename: str, clock: Callable[[], datetime]) -> Report:
    return ingest(repo, read_file(filename), filename, clock)
