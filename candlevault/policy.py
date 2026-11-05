"""Precedência de idempotência, proteção e atualização cumulativa."""
from .domain import Candle


def classify(old: Candle | None, new: Candle) -> tuple[str, str]:
    if old is None:
        return 'inseridos', 'chave nova'
    same = old.same_domain(new)
    if same and old.snapshot_at == new.snapshot_at:
        return 'ignorados', 'duplicação exata'
    if old.is_closed:
        return ('ignorados', 'fechado com conteúdo igual') if same else (
            'rejeitados', 'conflito: candle fechado protegido')
    if new.snapshot_at < old.snapshot_at:
        return 'ignorados', 'snapshot obsoleto'
    if new.snapshot_at == old.snapshot_at:
        return 'rejeitados', 'conflito no mesmo snapshot_at'
    if (new.open != old.open or new.high < old.high or new.low > old.low
            or new.volume < old.volume):
        return 'rejeitados', 'snapshot viola evolução cumulativa de open/high/low/volume'
    return 'atualizados', 'snapshot posterior aceito'
