"""
Implementação de referência da skill cycle-time-ndd.

Calcula o Cycle Time de work items da NDD em horas/dias úteis, a partir do
histórico real de mudança de status. Ver SKILL.md e docs/DOCUMENTACAO.md
para as regras completas.

Este módulo não depende de nenhum sistema externo (Azure DevOps, Jira,
etc.) — ele recebe uma lista de transições de status já extraída e um
objeto de configuração, e devolve o resultado do cálculo. Isso permite
reaproveitar a mesma lógica em Python, e serve de especificação para
portar o algoritmo para Power Query, SQL ou outra linguagem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional, Sequence


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalendarConfig:
    """Regras de calendário útil. Tudo configurável, com defaults da NDD."""

    work_start: time = time(8, 0)
    work_end: time = time(17, 0)
    lunch_start: time = time(12, 0)
    lunch_end: time = time(13, 0)
    # segunda=0 ... domingo=6 (padrão datetime.weekday()); sáb/dom de fora.
    business_weekdays: frozenset[int] = field(
        default_factory=lambda: frozenset({0, 1, 2, 3, 4})
    )
    holidays: frozenset[date] = field(default_factory=frozenset)

    def business_intervals_for_day(self, day: date) -> list[tuple[datetime, datetime]]:
        """Janelas úteis de um dia (antes e depois do almoço), já vazias
        se o dia não for útil (fim de semana/feriado)."""
        if day.weekday() not in self.business_weekdays or day in self.holidays:
            return []
        return [
            (datetime.combine(day, self.work_start), datetime.combine(day, self.lunch_start)),
            (datetime.combine(day, self.lunch_end), datetime.combine(day, self.work_end)),
        ]

    @property
    def hours_per_day(self) -> float:
        full_day = datetime.combine(date.min, self.work_end) - datetime.combine(date.min, self.work_start)
        lunch = datetime.combine(date.min, self.lunch_end) - datetime.combine(date.min, self.lunch_start)
        return (full_day - lunch).total_seconds() / 3600.0


@dataclass(frozen=True)
class StatusConfig:
    """Quais status marcam início e fim do Cycle Time. Configurável para
    incluir equivalências futuras (novos boards, outros idiomas etc.)."""

    execution_statuses: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"Active", "In Development", "In Progress", "Doing", "Em andamento"}
        )
    )
    final_statuses: frozenset[str] = field(
        default_factory=lambda: frozenset({"Resolved", "Closed"})
    )

    @staticmethod
    def _normalize(status: str) -> str:
        return status.strip().casefold()

    def is_execution(self, status: str) -> bool:
        normalized = {self._normalize(s) for s in self.execution_statuses}
        return self._normalize(status) in normalized

    def is_final(self, status: str) -> bool:
        normalized = {self._normalize(s) for s in self.final_statuses}
        return self._normalize(status) in normalized


@dataclass(frozen=True)
class WorkItemTypeConfig:
    """Classificação do work item em 'Valor' ou 'Issue'. Configurável."""

    value_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"Sprint Task", "User Story", "Spike"})
    )
    issue_types: frozenset[str] = field(default_factory=lambda: frozenset({"Issue"}))

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()

    def classify(self, work_item_type: Optional[str]) -> Optional[str]:
        if not work_item_type:
            return None
        wt = self._normalize(work_item_type)
        if wt in {self._normalize(v) for v in self.value_types}:
            return "Valor"
        if wt in {self._normalize(v) for v in self.issue_types}:
            return "Issue"
        return None


@dataclass(frozen=True)
class CycleTimeConfig:
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    statuses: StatusConfig = field(default_factory=StatusConfig)
    types: WorkItemTypeConfig = field(default_factory=WorkItemTypeConfig)
    min_valid_business_days: float = 0.01


# ---------------------------------------------------------------------------
# Entrada / Saída
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StatusChange:
    """Uma transição real de status, extraída do histórico do work item."""

    status: str
    changed_at: datetime


class CycleTimeInvalidReason:
    NO_EXECUTION_STATUS = "Sem status de execução"
    NOT_COMPLETED = "Item não concluído"
    INSUFFICIENT_HISTORY = "Histórico insuficiente"
    BELOW_NOISE_THRESHOLD = "Cycle Time <= 0,01 dia útil"


@dataclass
class CycleTimeResult:
    cycle_time_horas_uteis: Optional[float] = None
    cycle_time_dias_uteis: Optional[float] = None
    data_inicio_cycle_time: Optional[datetime] = None
    data_fim_cycle_time: Optional[datetime] = None
    tipo_cycle_time: Optional[str] = None
    cycle_time_valido: bool = False
    motivo_invalidacao: Optional[str] = None


# ---------------------------------------------------------------------------
# Núcleo do cálculo
# ---------------------------------------------------------------------------

def business_hours_between(start: datetime, end: datetime, calendar: CalendarConfig) -> float:
    """Horas úteis entre dois instantes, início inclusivo / fim exclusivo.

    Soma, dia a dia, a interseção de [start, end) com as janelas úteis do
    dia (manhã e tarde, descontando o almoço). Fins de semana e feriados
    contribuem zero. Instantes fora do expediente são automaticamente
    "clampados" pelas janelas do dia (ex.: item aberto antes das 08:00 só
    passa a contar às 08:00; item concluído depois das 17:00 só conta até
    as 17:00).
    """
    if end <= start:
        return 0.0

    total = timedelta()
    day = start.date()
    last_day = end.date()
    while day <= last_day:
        for interval_start, interval_end in calendar.business_intervals_for_day(day):
            overlap_start = max(start, interval_start)
            overlap_end = min(end, interval_end)
            if overlap_end > overlap_start:
                total += overlap_end - overlap_start
        day += timedelta(days=1)

    return total.total_seconds() / 3600.0


def _find_cycle_start(history: Sequence[StatusChange], statuses: StatusConfig) -> Optional[StatusChange]:
    """Primeira entrada real em status de execução. Não reinicia o
    relógio em entradas/saídas posteriores (regra 13)."""
    for change in history:
        if statuses.is_execution(change.status):
            return change
    return None


def _find_cycle_end(
    history: Sequence[StatusChange], start: StatusChange, statuses: StatusConfig
) -> Optional[StatusChange]:
    """Primeira entrada em status final que ocorre após o início do
    Cycle Time."""
    for change in history:
        if change.changed_at <= start.changed_at:
            continue
        if statuses.is_final(change.status):
            return change
    return None


def calculate_cycle_time(
    history: Optional[Iterable[StatusChange]],
    work_item_type: Optional[str] = None,
    config: Optional[CycleTimeConfig] = None,
) -> CycleTimeResult:
    """Calcula o Cycle Time de um work item a partir do histórico real de
    mudança de status.

    `history` deve vir ordenado ou não (a função ordena internamente por
    `changed_at`); cada elemento é uma transição real observada no board,
    nunca uma data inferida ou interpolada.
    """
    config = config or CycleTimeConfig()
    tipo = config.types.classify(work_item_type)

    if history is None:
        return CycleTimeResult(
            tipo_cycle_time=tipo,
            cycle_time_valido=False,
            motivo_invalidacao=CycleTimeInvalidReason.INSUFFICIENT_HISTORY,
        )

    ordered = sorted(history, key=lambda c: c.changed_at)
    if len(ordered) == 0:
        return CycleTimeResult(
            tipo_cycle_time=tipo,
            cycle_time_valido=False,
            motivo_invalidacao=CycleTimeInvalidReason.INSUFFICIENT_HISTORY,
        )

    start = _find_cycle_start(ordered, config.statuses)
    if start is None:
        return CycleTimeResult(
            tipo_cycle_time=tipo,
            cycle_time_valido=False,
            motivo_invalidacao=CycleTimeInvalidReason.NO_EXECUTION_STATUS,
        )

    end = _find_cycle_end(ordered, start, config.statuses)
    if end is None:
        return CycleTimeResult(
            data_inicio_cycle_time=start.changed_at,
            tipo_cycle_time=tipo,
            cycle_time_valido=False,
            motivo_invalidacao=CycleTimeInvalidReason.NOT_COMPLETED,
        )

    horas_uteis = business_hours_between(start.changed_at, end.changed_at, config.calendar)
    dias_uteis = horas_uteis / config.calendar.hours_per_day

    if dias_uteis <= config.min_valid_business_days:
        return CycleTimeResult(
            cycle_time_horas_uteis=horas_uteis,
            cycle_time_dias_uteis=dias_uteis,
            data_inicio_cycle_time=start.changed_at,
            data_fim_cycle_time=end.changed_at,
            tipo_cycle_time=tipo,
            cycle_time_valido=False,
            motivo_invalidacao=CycleTimeInvalidReason.BELOW_NOISE_THRESHOLD,
        )

    return CycleTimeResult(
        cycle_time_horas_uteis=horas_uteis,
        cycle_time_dias_uteis=dias_uteis,
        data_inicio_cycle_time=start.changed_at,
        data_fim_cycle_time=end.changed_at,
        tipo_cycle_time=tipo,
        cycle_time_valido=True,
        motivo_invalidacao=None,
    )
