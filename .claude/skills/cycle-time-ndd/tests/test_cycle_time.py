"""
Testes obrigatórios da skill cycle-time-ndd (ver SKILL.md, item 12).

Rode com: python -m pytest .claude/skills/cycle-time-ndd/tests -v
(ou apenas `python -m unittest` a partir desta pasta, sem dependências
externas).
"""

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference"))

from cycle_time import (  # noqa: E402
    CalendarConfig,
    CycleTimeConfig,
    CycleTimeInvalidReason,
    StatusChange,
    calculate_cycle_time,
)


def dt(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi)


class CycleTimeTests(unittest.TestCase):
    def setUp(self):
        # Segunda-feira 2024-01-01 é feriado (Confraternização Universal)
        self.config = CycleTimeConfig(
            calendar=CalendarConfig(holidays=frozenset({date(2024, 1, 1)}))
        )

    # 1) item iniciado e concluído no mesmo dia
    def test_same_day(self):
        history = [
            StatusChange("New", dt(2024, 1, 8, 8, 0)),
            StatusChange("In Progress", dt(2024, 1, 8, 9, 0)),  # terça
            StatusChange("Resolved", dt(2024, 1, 8, 11, 0)),
        ]
        result = calculate_cycle_time(history, "Sprint Task", self.config)
        self.assertTrue(result.cycle_time_valido)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 2.0)
        self.assertAlmostEqual(result.cycle_time_dias_uteis, 2.0 / 8.0)
        self.assertEqual(result.tipo_cycle_time, "Valor")

    # 2) item atravessando fim de semana
    def test_crosses_weekend(self):
        # sexta 2024-01-05 09:00 -> segunda 2024-01-08 10:00
        history = [
            StatusChange("In Progress", dt(2024, 1, 5, 9, 0)),
            StatusChange("Closed", dt(2024, 1, 8, 10, 0)),
        ]
        result = calculate_cycle_time(history, "Issue", self.config)
        self.assertTrue(result.cycle_time_valido)
        # sexta: 09:00-12:00 (3h) + 13:00-17:00 (4h) = 7h; segunda: 08:00-10:00 (2h)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 9.0)
        self.assertEqual(result.tipo_cycle_time, "Issue")

    # 3) item atravessando feriado
    def test_crosses_holiday(self):
        # sexta 2023-12-29 16:00 -> terça 2024-01-02 09:00, com feriado em 01-01 (segunda)
        history = [
            StatusChange("Doing", dt(2023, 12, 29, 16, 0)),
            StatusChange("Resolved", dt(2024, 1, 2, 9, 0)),
        ]
        result = calculate_cycle_time(history, "User Story", self.config)
        self.assertTrue(result.cycle_time_valido)
        # sexta: 16:00-17:00 (1h); sáb/dom fora; feriado 01-01 fora; terça: 08:00-09:00 (1h)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 2.0)

    # 4) item iniciado antes das 08:00
    def test_started_before_business_hours(self):
        history = [
            StatusChange("Active", dt(2024, 1, 8, 6, 0)),
            StatusChange("Resolved", dt(2024, 1, 8, 9, 0)),
        ]
        result = calculate_cycle_time(history, "Spike", self.config)
        self.assertTrue(result.cycle_time_valido)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 1.0)  # clampado às 08:00

    # 5) item iniciado depois das 17:00
    def test_started_after_business_hours(self):
        history = [
            StatusChange("Active", dt(2024, 1, 8, 19, 0)),
            StatusChange("Resolved", dt(2024, 1, 9, 9, 0)),
        ]
        result = calculate_cycle_time(history, "Spike", self.config)
        self.assertTrue(result.cycle_time_valido)
        # nada em 08/01 após 17h; 09/01: 08:00-09:00 (1h)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 1.0)

    # 6) item concluído fora do horário útil
    def test_ended_after_business_hours(self):
        history = [
            StatusChange("Active", dt(2024, 1, 8, 16, 0)),
            StatusChange("Resolved", dt(2024, 1, 8, 20, 0)),
        ]
        result = calculate_cycle_time(history, "Spike", self.config)
        self.assertTrue(result.cycle_time_valido)
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 1.0)  # clampado às 17:00

    # 7) item sem status de execução
    def test_no_execution_status(self):
        history = [
            StatusChange("New", dt(2024, 1, 8, 8, 0)),
            StatusChange("Resolved", dt(2024, 1, 8, 11, 0)),
        ]
        result = calculate_cycle_time(history, "Issue", self.config)
        self.assertFalse(result.cycle_time_valido)
        self.assertEqual(result.motivo_invalidacao, CycleTimeInvalidReason.NO_EXECUTION_STATUS)
        self.assertIsNone(result.cycle_time_horas_uteis)

    # 8) item ainda aberto (nunca chegou a status final)
    def test_still_open(self):
        history = [
            StatusChange("In Progress", dt(2024, 1, 8, 8, 0)),
        ]
        result = calculate_cycle_time(history, "User Story", self.config)
        self.assertFalse(result.cycle_time_valido)
        self.assertEqual(result.motivo_invalidacao, CycleTimeInvalidReason.NOT_COMPLETED)
        self.assertEqual(result.data_inicio_cycle_time, dt(2024, 1, 8, 8, 0))
        self.assertIsNone(result.cycle_time_horas_uteis)

    # 9) item com Cycle Time <= 0,01 dia útil (ruído)
    def test_below_noise_threshold(self):
        history = [
            StatusChange("Doing", dt(2024, 1, 8, 8, 0)),
            StatusChange("Closed", dt(2024, 1, 8, 8, 2)),  # 2 minutos
        ]
        result = calculate_cycle_time(history, "Sprint Task", self.config)
        self.assertFalse(result.cycle_time_valido)
        self.assertEqual(result.motivo_invalidacao, CycleTimeInvalidReason.BELOW_NOISE_THRESHOLD)
        self.assertIsNotNone(result.cycle_time_dias_uteis)  # valor calculado, só não é válido p/ agregação

    # 10) item com múltiplas entradas e saídas de status de execução:
    #     usar a PRIMEIRA entrada, sem reiniciar o relógio
    def test_multiple_execution_entries_uses_first(self):
        history = [
            StatusChange("In Progress", dt(2024, 1, 8, 8, 0)),   # 1a entrada -> início real
            StatusChange("Blocked", dt(2024, 1, 8, 10, 0)),
            StatusChange("In Progress", dt(2024, 1, 8, 12, 0)),  # reentrada, não reinicia
            StatusChange("Resolved", dt(2024, 1, 8, 15, 0)),
        ]
        result = calculate_cycle_time(history, "Sprint Task", self.config)
        self.assertTrue(result.cycle_time_valido)
        self.assertEqual(result.data_inicio_cycle_time, dt(2024, 1, 8, 8, 0))
        # 08:00-15:00 útil, descontando almoço 12:00-13:00 => 6h
        self.assertAlmostEqual(result.cycle_time_horas_uteis, 6.0)

    # extra: histórico ausente/vazio -> não calculável (não confundir com "sem status de execução")
    def test_insufficient_history(self):
        result = calculate_cycle_time([], "Issue", self.config)
        self.assertFalse(result.cycle_time_valido)
        self.assertEqual(result.motivo_invalidacao, CycleTimeInvalidReason.INSUFFICIENT_HISTORY)

        result_none = calculate_cycle_time(None, "Issue", self.config)
        self.assertFalse(result_none.cycle_time_valido)
        self.assertEqual(result_none.motivo_invalidacao, CycleTimeInvalidReason.INSUFFICIENT_HISTORY)

    # extra: tipo de work item não mapeado -> TipoCycleTime nulo, cálculo segue normal
    def test_unmapped_work_item_type(self):
        history = [
            StatusChange("Active", dt(2024, 1, 8, 8, 0)),
            StatusChange("Resolved", dt(2024, 1, 8, 9, 0)),
        ]
        result = calculate_cycle_time(history, "Bug", self.config)
        self.assertIsNone(result.tipo_cycle_time)
        self.assertTrue(result.cycle_time_valido)


if __name__ == "__main__":
    unittest.main()
