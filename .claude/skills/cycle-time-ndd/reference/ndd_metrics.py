"""
Implementação de referência da skill cycle-time-ndd — Lead Time, Cycle
Time, WIP e Espera, replicando exatamente as regras do painel
"Indicadores Operacionais DevOps" (BIOperacional) da NDD.

Este arquivo é a fonte da verdade executável. Qualquer porte para outra
linguagem (SQL, Power Query etc.) deve reproduzir fielmente cada regra
aqui, inclusive as que parecem "estranhas" (ex.: a fórmula do Cycle Time
usa uma aproximação por dias úteis + delta de hora do dia, não uma soma
exata de intervalos — é assim que o painel oficial calcula).

Ver docs/DOCUMENTACAO.md para a explicação de cada regra e exemplos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Sequence


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BusinessCalendar:
    """Calendário útil. O painel usa uma TABELA de dias úteis (hoje 249
    dias úteis em 365, já com feriados descontados) — não uma regra de
    "segunda a sexta". Aqui isso é modelado como uma lista explícita de
    feriados sobre os dias de semana configurados; se a tabela oficial de
    calendário estiver disponível como lista de datas úteis, ela pode ser
    injetada diretamente via `explicit_business_dates` para bater 1:1 com
    a fonte."""

    business_weekdays: frozenset[int] = field(
        default_factory=lambda: frozenset({0, 1, 2, 3, 4})  # seg=0 ... dom=6
    )
    holidays: frozenset[date] = field(default_factory=frozenset)
    # Jornada útil: 08:00-12:00 e 13:30-17:30 (8h/dia, já sem almoço).
    journey_blocks: tuple[tuple[time, time], ...] = (
        (time(8, 0), time(12, 0)),
        (time(13, 30), time(17, 30)),
    )
    explicit_business_dates: Optional[frozenset[date]] = None

    @property
    def hours_per_day(self) -> float:
        total = timedelta()
        for block_start, block_end in self.journey_blocks:
            total += datetime.combine(date.min, block_end) - datetime.combine(date.min, block_start)
        return total.total_seconds() / 3600.0

    def is_business_day(self, day: date) -> bool:
        if self.explicit_business_dates is not None:
            return day in self.explicit_business_dates
        return day.weekday() in self.business_weekdays and day not in self.holidays

    def business_days_between_exclusive_start(self, start_date: date, end_date: date) -> int:
        """dias_úteis(início, fim] — exclusivo no início, inclusivo no fim."""
        if end_date <= start_date:
            return 0
        count = 0
        day = start_date + timedelta(days=1)
        while day <= end_date:
            if self.is_business_day(day):
                count += 1
            day += timedelta(days=1)
        return count

    def journey_blocks_for_day(self, day: date) -> list[tuple[datetime, datetime]]:
        if not self.is_business_day(day):
            return []
        return [
            (datetime.combine(day, block_start), datetime.combine(day, block_end))
            for block_start, block_end in self.journey_blocks
        ]

    def business_hours_in_interval(self, start: datetime, end: datetime) -> float:
        """Soma exata da interseção de [start, end) com a jornada útil,
        dia a dia. Usada para Espera (fila) — não para o Cycle Time, cuja
        fórmula oficial é a aproximação de `cycle_time_hours`."""
        if end <= start:
            return 0.0
        total = timedelta()
        day = start.date()
        last_day = end.date()
        while day <= last_day:
            for block_start, block_end in self.journey_blocks_for_day(day):
                overlap_start = max(start, block_start)
                overlap_end = min(end, block_end)
                if overlap_end > overlap_start:
                    total += overlap_end - overlap_start
            day += timedelta(days=1)
        return total.total_seconds() / 3600.0


@dataclass(frozen=True)
class BlockingConfig:
    """Mecanismos de bloqueio: tags configuráveis e um campo customizado
    por (collection, project)."""

    # Lista confirmada na tela de configuração de produção ("Tags
    # Bloqueantes (Horas)"), 9 de 4.469 tags distintas. A comparação é
    # sensível a maiúsculas/minúsculas e exata — "bloqueado" em minúsculas
    # (726 ocorrências) está deliberadamente FORA da lista, apesar de mais
    # frequente que várias tags marcadas. Nunca ampliar por semelhança.
    tags: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "Bloqueado",
                "#Bloqueado",
                "Bloqueio",
                "Bloqueada",
                "Bloqueado - Ambiente/Infra",
                "Bloqueado - Prioridade",
                "Bloqueado - Outros Times",
                "Bloqueado - Pendência Técnica",
                "bloque",
            }
        )
    )
    # (collection, project) -> (nome do campo, padrão regex que indica bloqueio)
    custom_fields: dict[tuple[str, str], tuple[str, str]] = field(
        default_factory=lambda: {
            ("NDD-PrintCollection", "nddPrint-360"): ("Ndd.Bloqueio", r"^Bloqueado"),
            ("NDD Orbix", "Orbix Geral"): ("Custom.Bloqueio", r"^Bloqueado"),
        }
    )

    def is_blocking_tag(self, tag: str) -> bool:
        """Correspondência EXATA e sensível a maiúsculas/minúsculas —
        confirmado em produção que variantes de caixa (ex.: "bloqueado"
        minúsculo) não contam, mesmo sendo mais frequentes que tags
        marcadas. Não normalizar aqui."""
        return tag in self.tags

    def field_for(self, collection: str, project: str) -> Optional[tuple[str, str]]:
        return self.custom_fields.get((collection, project))

    def field_value_blocks(self, collection: str, project: str, value: Optional[str]) -> bool:
        mapping = self.field_for(collection, project)
        if mapping is None or value is None:
            return False
        _, pattern = mapping
        return re.match(pattern, value) is not None


@dataclass(frozen=True)
class StatusConfig:
    """Estados ativos vêm de config_active_hours_states (hoje 38 estados).
    Qualquer estado fora dessa lista é considerado "fila" (espera) para
    fins da métrica de Espera."""

    active_states: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "Active",
                "In Development",
                "Analysis",
                "In Test",
                "Development",
                "Testing",
                "Doing",
                "In Progress",
                "Code Review",
                "Em andamento",
                # Representativo — a lista real de produção tem 38 estados,
                # mantida em config_active_hours_states. Complete/ajuste
                # aqui para bater com a tabela oficial.
            }
        )
    )
    wait_states: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "Awaiting Test",
                "Awaiting Code Review",
                "Awaiting Analysis",
                "Awaiting Review",
                "Ready for Dev",
            }
        )
    )

    @staticmethod
    def _normalize(status: str) -> str:
        return status.strip().casefold()

    def is_active(self, status: str) -> bool:
        normalized = {self._normalize(s) for s in self.active_states}
        return self._normalize(status) in normalized


@dataclass(frozen=True)
class WorkItemTypeConfig:
    accepted_types: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"Bug", "Issue", "User Story", "Sprint Task", "Spike", "Homologation Item"}
        )
    )

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()

    def is_accepted(self, work_item_type: Optional[str]) -> bool:
        if not work_item_type:
            return False
        return self._normalize(work_item_type) in {self._normalize(v) for v in self.accepted_types}


@dataclass(frozen=True)
class NddMetricsConfig:
    calendar: BusinessCalendar = field(default_factory=BusinessCalendar)
    statuses: StatusConfig = field(default_factory=StatusConfig)
    blocking: BlockingConfig = field(default_factory=BlockingConfig)
    types: WorkItemTypeConfig = field(default_factory=WorkItemTypeConfig)
    min_cycle_time_hours: float = 0.5
    # config_excluded_cycle_time: chaves (collection, project, id) fora do
    # cycle time/throughput nos KPIs da home. Hoje vazia em produção.
    excluded_cycle_time_keys: frozenset[tuple[str, str, str]] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StatusChange:
    """Transição real de status do work item (histórico do TFS/Azure
    DevOps). Nunca uma data inferida."""

    status: str
    changed_at: datetime


@dataclass(frozen=True)
class TagInterval:
    """Período em que uma tag esteve presente no work item. `end=None`
    significa que a tag segue presente (ainda não foi removida)."""

    tag: str
    start: datetime
    end: Optional[datetime]


@dataclass(frozen=True)
class FieldInterval:
    """Período em que o campo customizado de bloqueio teve um dado valor.
    `end=None` significa que o valor é o atual (ainda não mudou)."""

    value: Optional[str]
    start: datetime
    end: Optional[datetime]


@dataclass(frozen=True)
class WorkItem:
    collection: str
    project: str
    id: str
    work_item_type: str
    area_path: str
    created_date: datetime
    closed_date: Optional[datetime]
    activated_date: Optional[datetime]
    status_history: Sequence[StatusChange] = field(default_factory=tuple)
    tag_intervals: Sequence[TagInterval] = field(default_factory=tuple)
    field_intervals: Sequence[FieldInterval] = field(default_factory=tuple)

    @property
    def key(self) -> tuple[str, str, str]:
        """Chave única do work item. Id NÃO é único entre coleções — todo
        agrupamento/junção deve usar (collection, project, id)."""
        return (self.collection, self.project, self.id)


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------

@dataclass
class NddMetricsResult:
    lead_time_dias_uteis: Optional[float] = None
    cycle_time_horas_uteis: Optional[float] = None
    cycle_time_dias_uteis: Optional[float] = None
    wip_horas_uteis: Optional[float] = None
    wip_dias_uteis: Optional[float] = None
    espera_dias_uteis: Optional[float] = None
    data_inicio_trabalho: Optional[datetime] = None
    data_fechamento: Optional[datetime] = None
    excluido_kpi: bool = False
    cycle_time_zero_para_kpi: bool = False


# ---------------------------------------------------------------------------
# Núcleo do cálculo
# ---------------------------------------------------------------------------

def determine_work_start(
    activated_date: Optional[datetime],
    status_history: Sequence[StatusChange],
    statuses: StatusConfig,
) -> Optional[datetime]:
    """início = LEAST(activated_date, primeira entrada em estado ativo),
    ignorando nulos — basta um dos dois existir."""
    candidates: list[datetime] = []
    if activated_date is not None:
        candidates.append(activated_date)
    for change in sorted(status_history, key=lambda c: c.changed_at):
        if statuses.is_active(change.status):
            candidates.append(change.changed_at)
            break
    return min(candidates) if candidates else None


def _capped_field_end(
    interval: FieldInterval, closed_date: Optional[datetime], now: datetime
) -> datetime:
    """O período do campo de bloqueio é travado no fechamento:
    MENOR(fim_do_bloqueio, closed_date, agora)."""
    candidates = [now]
    if interval.end is not None:
        candidates.append(interval.end)
    if closed_date is not None:
        candidates.append(closed_date)
    return min(candidates)


def blocked_business_days(
    item: WorkItem,
    window_start: datetime,
    window_end: datetime,
    calendar: BusinessCalendar,
    blocking: BlockingConfig,
    now: datetime,
) -> set[date]:
    """Dias úteis dentro de [window_start, window_end] em que o item
    estava bloqueado por tag e/ou campo customizado. União de dias
    distintos — um dia coberto pelos dois mecanismos conta uma vez."""
    blocked_days: set[date] = set()

    def _mark(interval_start: datetime, interval_end: datetime) -> None:
        start = max(interval_start, window_start)
        end = min(interval_end, window_end)
        if end <= start:
            return
        day = start.date()
        while day <= end.date():
            if calendar.is_business_day(day):
                blocked_days.add(day)
            day += timedelta(days=1)

    for tag_interval in item.tag_intervals:
        if not blocking.is_blocking_tag(tag_interval.tag):
            continue
        end = tag_interval.end if tag_interval.end is not None else now
        _mark(tag_interval.start, end)

    for field_interval in item.field_intervals:
        if not blocking.field_value_blocks(item.collection, item.project, field_interval.value):
            continue
        end = _capped_field_end(field_interval, item.closed_date, now)
        _mark(field_interval.start, end)

    return blocked_days


def _minutes_of_day(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def cycle_time_hours(
    item: WorkItem,
    config: NddMetricsConfig,
    now: Optional[datetime] = None,
) -> tuple[Optional[float], Optional[datetime]]:
    """Retorna (CycleTimeHorasUteis, DataInicioTrabalho).

    SE closed_date é nulo           -> (None, início)   # item aberto = WIP, não cycle time
    SE início é nulo                -> (None, None)
    SE início e fechamento no MESMO DIA -> diferença bruta em horas
    SENÃO -> MAIOR(0,5 ; dias_úteis(início, fechamento] × 8
                        + (hora:min do fechamento − hora:min do início)
                        − horas_bloqueadas)
    """
    now = now or datetime.now()
    start = determine_work_start(item.activated_date, item.status_history, config.statuses)

    if item.closed_date is None:
        return None, start
    if start is None:
        return None, None

    end = item.closed_date

    if start.date() == end.date():
        return (end - start).total_seconds() / 3600.0, start

    business_days = config.calendar.business_days_between_exclusive_start(start.date(), end.date())
    clock_delta_hours = (_minutes_of_day(end) - _minutes_of_day(start)) / 60.0
    blocked_days = blocked_business_days(item, start, end, config.calendar, config.blocking, now)
    blocked_hours = len(blocked_days) * config.calendar.hours_per_day

    raw_hours = business_days * config.calendar.hours_per_day + clock_delta_hours - blocked_hours
    return max(config.min_cycle_time_hours, raw_hours), start


def wip_hours(
    item: WorkItem,
    config: NddMetricsConfig,
    now: Optional[datetime] = None,
) -> tuple[Optional[float], Optional[datetime]]:
    """WIP = início do trabalho → agora, mesmo calendário e mesmo
    desconto de bloqueio do Cycle Time. Só existe em item aberto —
    mutuamente exclusivo com Cycle Time."""
    now = now or datetime.now()
    if item.closed_date is not None:
        return None, None

    start = determine_work_start(item.activated_date, item.status_history, config.statuses)
    if start is None:
        return None, None

    if start.date() == now.date():
        return (now - start).total_seconds() / 3600.0, start

    business_days = config.calendar.business_days_between_exclusive_start(start.date(), now.date())
    clock_delta_hours = (_minutes_of_day(now) - _minutes_of_day(start)) / 60.0
    blocked_days = blocked_business_days(item, start, now, config.calendar, config.blocking, now)
    blocked_hours = len(blocked_days) * config.calendar.hours_per_day

    raw_hours = business_days * config.calendar.hours_per_day + clock_delta_hours - blocked_hours
    return max(config.min_cycle_time_hours, raw_hours), start


def lead_time_business_days(item: WorkItem, config: NddMetricsConfig) -> Optional[float]:
    """Lead Time = created_date -> closed_date, em dias úteis, contando a
    fila inteira (sem descontar bloqueio nem espera). Usa a mesma
    convenção de calendário do Cycle Time: exclusivo no início, inclusivo
    no fim."""
    if item.created_date is None or item.closed_date is None:
        return None
    return float(
        config.calendar.business_days_between_exclusive_start(
            item.created_date.date(), item.closed_date.date()
        )
    )


def espera_business_days(
    item: WorkItem,
    start: Optional[datetime],
    config: NddMetricsConfig,
) -> Optional[float]:
    """Espera = horas úteis, dentro da janela [início, fechamento], em que
    o item esteve em estado não-ativo (fila), convertidas em dias úteis.
    Não é descontada do Cycle Time — anda ao lado dele."""
    if start is None or item.closed_date is None:
        return None

    ordered = sorted(item.status_history, key=lambda c: c.changed_at)
    if not ordered:
        return None

    total_hours = 0.0
    for current, nxt in zip(ordered, ordered[1:]):
        segment_start = max(current.changed_at, start)
        segment_end = min(nxt.changed_at, item.closed_date)
        if segment_end <= segment_start:
            continue
        if not config.statuses.is_active(current.status):
            total_hours += config.calendar.business_hours_in_interval(segment_start, segment_end)

    last = ordered[-1]
    if last.changed_at < item.closed_date and not config.statuses.is_active(last.status):
        segment_start = max(last.changed_at, start)
        total_hours += config.calendar.business_hours_in_interval(segment_start, item.closed_date)

    return total_hours / config.calendar.hours_per_day


def calculate_metrics(
    item: WorkItem,
    config: Optional[NddMetricsConfig] = None,
    now: Optional[datetime] = None,
) -> NddMetricsResult:
    """Calcula Lead Time, Cycle Time, WIP e Espera de um work item,
    seguindo exatamente as regras do painel BIOperacional."""
    config = config or NddMetricsConfig()
    now = now or datetime.now()

    cycle_hours, start = cycle_time_hours(item, config, now)
    wip_h, wip_start = wip_hours(item, config, now)
    effective_start = start if start is not None else wip_start

    cycle_days = cycle_hours / config.calendar.hours_per_day if cycle_hours is not None else None
    wip_days = wip_h / config.calendar.hours_per_day if wip_h is not None else None

    lead_days = lead_time_business_days(item, config)
    espera_days = espera_business_days(item, start, config)

    excluded = item.key in config.excluded_cycle_time_keys
    zero_for_kpi = cycle_days is not None and round_half_up(cycle_days, 1) == 0.0

    return NddMetricsResult(
        lead_time_dias_uteis=lead_days,
        cycle_time_horas_uteis=cycle_hours,
        cycle_time_dias_uteis=cycle_days,
        wip_horas_uteis=wip_h,
        wip_dias_uteis=wip_days,
        espera_dias_uteis=espera_days,
        data_inicio_trabalho=effective_start,
        data_fechamento=item.closed_date,
        excluido_kpi=excluded,
        cycle_time_zero_para_kpi=zero_for_kpi,
    )


def is_valid_for_kpi_average(result: NddMetricsResult) -> bool:
    """Filtro a aplicar antes de calcular médias/indicadores agregados:
    fora itens excluídos por configuração e itens cujo cycle time
    arredonda para zero (fechados em segundos, sem ciclo real)."""
    return (
        result.cycle_time_dias_uteis is not None
        and not result.excluido_kpi
        and not result.cycle_time_zero_para_kpi
    )


# ---------------------------------------------------------------------------
# Arredondamento
# ---------------------------------------------------------------------------

def round_half_up(value: float, decimals: int = 1) -> float:
    """Arredondamento meio para cima (2,35 -> 2,4), usando Decimal para
    evitar o erro de ponto flutuante que faz uma média em .x5 oscilar
    entre execuções."""
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def average_rounded(values: Sequence[float], decimals: int = 1) -> Optional[float]:
    """Média calculada em Decimal exato (não em ponto flutuante), depois
    arredondada meio para cima."""
    if not values:
        return None
    total = sum(Decimal(str(v)) for v in values)
    avg = total / Decimal(len(values))
    quantum = Decimal(1).scaleb(-decimals)
    return float(avg.quantize(quantum, rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Filtros e chaves auxiliares
# ---------------------------------------------------------------------------

def normalize_team_name(area_path_or_team: str) -> str:
    """Time é resolvido pelo último segmento do AreaPath (separador \\ ou
    /), com a variação aceita do sufixo " team" (case-insensitive)."""
    segment = area_path_or_team.split("\\")[-1].split("/")[-1].strip()
    if segment.casefold().endswith(" team"):
        segment = segment[: -len(" team")].strip()
    return segment
