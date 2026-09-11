"""
Testes da skill cycle-time-ndd contra a fonte da verdade oficial (painel
BIOperacional). Rode com:

    python3 .claude/skills/cycle-time-ndd/tests/test_ndd_metrics.py -v
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference"))

from ndd_metrics import (  # noqa: E402
    BlockingConfig,
    BusinessCalendar,
    FieldInterval,
    NddMetricsConfig,
    StatusChange,
    StatusConfig,
    TagInterval,
    WorkItem,
    average_rounded,
    calculate_metrics,
    determine_work_start,
    is_valid_for_kpi_average,
    lead_time_business_days,
    normalize_team_name,
    round_half_up,
)


def dt(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi)


def make_item(**overrides):
    defaults = dict(
        collection="NDD-PrintCollection",
        project="nddPrint-360",
        id="1",
        work_item_type="Bug",
        area_path="NDD\\Print\\Squad Alpha",
        created_date=dt(2024, 1, 8, 8, 0),
        closed_date=None,
        activated_date=None,
        status_history=(),
        tag_intervals=(),
        field_intervals=(),
    )
    defaults.update(overrides)
    return WorkItem(**defaults)


class NddMetricsTests(unittest.TestCase):
    def setUp(self):
        self.config = NddMetricsConfig()

    # --- regra 2: início = LEAST(activated_date, primeira entrada ativa) ---

    def test_start_uses_first_active_state_when_activated_date_missing(self):
        # ~1 em 5 itens não tem ActivatedDate: vai de New direto para In Test.
        item = make_item(
            activated_date=None,
            status_history=[
                StatusChange("New", dt(2024, 1, 8, 8, 0)),
                StatusChange("In Test", dt(2024, 1, 9, 10, 0)),
            ],
        )
        start = determine_work_start(item.activated_date, item.status_history, self.config.statuses)
        self.assertEqual(start, dt(2024, 1, 9, 10, 0))

    def test_start_takes_least_of_activated_date_and_first_active_state(self):
        item = make_item(
            activated_date=dt(2024, 1, 10, 9, 0),
            status_history=[
                StatusChange("New", dt(2024, 1, 8, 8, 0)),
                StatusChange("In Test", dt(2024, 1, 9, 10, 0)),  # mais cedo que ActivatedDate
            ],
        )
        start = determine_work_start(item.activated_date, item.status_history, self.config.statuses)
        self.assertEqual(start, dt(2024, 1, 9, 10, 0))

    def test_wait_states_are_not_active(self):
        item = make_item(
            status_history=[StatusChange("Awaiting Test", dt(2024, 1, 8, 8, 0))],
        )
        start = determine_work_start(item.activated_date, item.status_history, self.config.statuses)
        self.assertIsNone(start)

    def test_no_start_detectable_is_none_not_zero(self):
        # ~1.900 itens fechados sem início detectável na base oficial: não entram na média.
        item = make_item(
            activated_date=None,
            status_history=[StatusChange("New", dt(2024, 1, 8, 8, 0))],
            closed_date=dt(2024, 1, 9, 10, 0),
        )
        result = calculate_metrics(item, self.config)
        self.assertIsNone(result.cycle_time_dias_uteis)
        self.assertFalse(is_valid_for_kpi_average(result))

    # --- regra 4: fórmula do Cycle Time ---

    def test_same_day_is_raw_difference(self):
        item = make_item(
            activated_date=dt(2024, 1, 8, 9, 0),
            closed_date=dt(2024, 1, 8, 11, 30),
        )
        result = calculate_metrics(item, self.config)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 2.5)

    def test_open_item_has_no_cycle_time_only_wip(self):
        item = make_item(
            activated_date=dt(2024, 1, 8, 9, 0),
            closed_date=None,
        )
        result = calculate_metrics(item, self.config, now=dt(2024, 1, 10, 12, 0))
        self.assertIsNone(result.cycle_time_dias_uteis)
        self.assertIsNotNone(result.wip_dias_uteis)
        # Cycle Time e WIP são mutuamente exclusivos.
        self.assertTrue((result.cycle_time_dias_uteis is None) != (result.wip_dias_uteis is None))

    def test_multi_day_formula_matches_official_approximation(self):
        # segunda 09:00 -> terça 15:00, sem bloqueio.
        item = make_item(
            activated_date=dt(2024, 1, 8, 9, 0),  # segunda
            closed_date=dt(2024, 1, 9, 15, 0),  # terça
        )
        result = calculate_metrics(item, self.config)
        # dias_uteis(seg, ter] = 1 dia -> 8h; + (15:00-09:00) = 6h -> 14h
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 14.0)

    def test_floor_of_half_hour_after_blocking_discount(self):
        # multi-dia, mas quase todo o tempo bloqueado -> não pode zerar, piso 0,5h.
        item = make_item(
            activated_date=dt(2024, 1, 8, 9, 0),
            closed_date=dt(2024, 1, 9, 9, 5),
            tag_intervals=[TagInterval("Bloqueado", dt(2024, 1, 8, 9, 0), dt(2024, 1, 9, 9, 5))],
        )
        result = calculate_metrics(item, self.config)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 0.5)

    # --- regra 5: desconto de bloqueio ---

    def test_blocked_day_discounts_full_8_hours(self):
        item = make_item(
            activated_date=dt(2024, 1, 8, 8, 0),  # segunda
            closed_date=dt(2024, 1, 10, 8, 0),  # quarta
            tag_intervals=[TagInterval("Bloqueado", dt(2024, 1, 9, 0, 0), dt(2024, 1, 9, 23, 59))],
        )
        result = calculate_metrics(item, self.config)
        # dias_uteis(seg,qua] = {ter, qua} = 2 dias -> 16h; delta hora = 0h; -8h bloqueado = 8h
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 8.0)

    def test_tag_and_field_blocking_same_day_counts_once(self):
        item = make_item(
            activated_date=dt(2024, 1, 8, 8, 0),
            closed_date=dt(2024, 1, 10, 8, 0),
            tag_intervals=[TagInterval("Bloqueado", dt(2024, 1, 9, 8, 0), dt(2024, 1, 9, 12, 0))],
            field_intervals=[FieldInterval("Bloqueado - Infra", dt(2024, 1, 9, 13, 0), dt(2024, 1, 9, 17, 0))],
        )
        result = calculate_metrics(item, self.config)
        # mesmo dia (09/01) coberto por tag E campo -> descontado uma vez só (8h), não 16h.
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 8.0)

    def test_field_blocking_capped_at_closed_date(self):
        item = make_item(
            activated_date=dt(2024, 1, 8, 8, 0),
            closed_date=dt(2024, 1, 9, 8, 0),
            # campo nunca "desbloqueado" (end=None) -> trava no closed_date, não acumula infinito.
            field_intervals=[FieldInterval("Bloqueado - Outros Times", dt(2024, 1, 8, 8, 0), None)],
        )
        result = calculate_metrics(item, self.config)
        self.assertIsNotNone(result.cycle_time_horas_uteis)
        self.assertGreaterEqual(result.cycle_time_horas_uteis, self.config.min_cycle_time_hours)

    # --- regra 6: exclusões e NULLIF(valor, 0) ---

    def test_excluded_item_flagged_for_kpi(self):
        item = make_item(id="42", activated_date=dt(2024, 1, 8, 9, 0), closed_date=dt(2024, 1, 8, 11, 0))
        config = NddMetricsConfig(excluded_cycle_time_keys=frozenset({item.key}))
        result = calculate_metrics(item, config)
        self.assertTrue(result.excluido_kpi)
        self.assertFalse(is_valid_for_kpi_average(result))
        # mas o valor continua calculado para relatórios detalhados.
        self.assertIsNotNone(result.cycle_time_dias_uteis)

    def test_cycle_time_rounding_to_zero_excluded_from_kpi(self):
        item = make_item(
            activated_date=datetime(2024, 1, 8, 9, 0, 0),
            closed_date=datetime(2024, 1, 8, 9, 0, 1),  # 1 segundo
        )
        result = calculate_metrics(item, self.config)
        self.assertTrue(result.cycle_time_zero_para_kpi)
        self.assertFalse(is_valid_for_kpi_average(result))

    # --- regra 7: WIP e Espera ---

    def test_espera_is_reported_alongside_not_subtracted(self):
        item = make_item(
            activated_date=dt(2024, 1, 8, 8, 0),
            closed_date=dt(2024, 1, 9, 12, 0),
            status_history=[
                StatusChange("In Development", dt(2024, 1, 8, 8, 0)),
                StatusChange("Awaiting Code Review", dt(2024, 1, 8, 12, 0)),
                StatusChange("In Development", dt(2024, 1, 9, 8, 0)),
            ],
        )
        result = calculate_metrics(item, self.config)
        self.assertIsNotNone(result.espera_dias_uteis)
        self.assertGreater(result.espera_dias_uteis, 0)
        # Espera não reduz o Cycle Time (a fórmula do Cycle Time não a desconta).
        self.assertIsNotNone(result.cycle_time_dias_uteis)

    # --- regra 8: arredondamento ---

    def test_round_half_up(self):
        self.assertEqual(round_half_up(2.35, 1), 2.4)
        self.assertEqual(round_half_up(2.34, 1), 2.3)

    def test_average_uses_decimal_not_float(self):
        # média que cairia em .x5 problemático em ponto flutuante puro.
        avg = average_rounded([1.15, 1.15, 1.15], decimals=1)
        self.assertEqual(avg, 1.2)

    # --- regra 9: chave composta e time ---

    def test_composite_key_distinguishes_same_id_across_collections(self):
        item_a = make_item(collection="NDD-PrintCollection", project="nddPrint-360", id="100")
        item_b = make_item(collection="NDD Orbix", project="Orbix Geral", id="100")
        self.assertNotEqual(item_a.key, item_b.key)

    def test_team_name_strips_team_suffix_variation(self):
        self.assertEqual(normalize_team_name("NDD\\Print\\Squad Alpha Team"), "Squad Alpha")
        self.assertEqual(normalize_team_name("NDD\\Print\\Squad Alpha"), "Squad Alpha")

    # --- regra 1: Lead Time e Cycle Time não são intercambiáveis ---

    def test_lead_time_counts_whole_queue_independent_of_blocking(self):
        item = make_item(
            created_date=dt(2024, 1, 5, 9, 0),  # sexta
            activated_date=dt(2024, 1, 9, 9, 0),  # terça seguinte (fila antes de começar)
            closed_date=dt(2024, 1, 10, 9, 0),  # quarta
            tag_intervals=[TagInterval("Bloqueado", dt(2024, 1, 9, 9, 0), dt(2024, 1, 9, 17, 0))],
        )
        lead = lead_time_business_days(item, self.config)
        cycle_result = calculate_metrics(item, self.config)
        # Lead Time conta a fila inteira (criação -> fechamento); Cycle Time só a partir do início do trabalho.
        self.assertGreater(lead, cycle_result.cycle_time_dias_uteis)


if __name__ == "__main__":
    unittest.main()
