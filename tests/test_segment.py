from __future__ import annotations

from co_extract.pipeline import ChangeOrderPipeline
from co_extract.segment import split_change_orders
from tests.conftest import SAMPLES


def test_single_order_is_not_split() -> None:
    text = (SAMPLES / "co_001_clean.txt").read_text(encoding="utf-8")
    assert split_change_orders(text) == [text]


def test_packet_splits_at_each_new_number_and_keeps_the_title_line() -> None:
    parts = split_change_orders((SAMPLES / "co_010_packet.txt").read_text(encoding="utf-8"))
    assert len(parts) == 2
    assert all(part.startswith("CHANGE ORDER") for part in parts)
    assert "CO-101" in parts[0]
    assert "CO-102" in parts[1]


def test_repeated_number_on_a_later_page_does_not_split() -> None:
    text = "Change Order No.: CO-5\nAmount: $1.00\n\nPage 2\nChange Order No.: CO-5\nmore"
    assert len(split_change_orders(text)) == 1


def test_run_packet_extracts_each_order(rules_pipeline: ChangeOrderPipeline) -> None:
    results = rules_pipeline.run_packet(SAMPLES / "co_010_packet.txt")
    assert [r.source for r in results] == ["co_010_packet.txt#1", "co_010_packet.txt#2"]
    assert [r.change_order.change_order_number.value for r in results] == ["CO-101", "CO-102"]
    assert [str(r.change_order.amount.value) for r in results] == ["1850.00", "-2400.00"]
