"""Seeded synthetic corpus: change-order texts whose true field values are known by construction.

The goal is volume and variety (layouts, label wording, date and money formats, OCR-style
damage), not realism: these are self-authored documents, so scores on them say how robust the
extractor is to the variations *we thought of*, not how it performs on real paperwork.

Usage: python -m co_extract.corpus OUT_DIR [--n 200] [--seed 7]
"""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECTS = [
    "Riverside Medical Center - East Wing",
    "Cedar Ridge School - Gym Addition",
    "Harbor Point Office Tower - Level 12 Fit-Out",
    "Maple Court Apartments - Building B",
    "Greenfield Community Pool - Filtration Upgrade",
    "Pioneer Square Garage - Level 4 Repairs",
    "Oakridge Public Library - Roof Replacement",
    "Sunset Hills Fire Station No. 7",
]
OWNERS = [
    "Riverside Health Partners LLC",
    "Cedar Ridge ISD",
    "Harbor Point Properties LP",
    "Maple Court Holdings LLC",
    "Greenfield Parks Department",
    "Pioneer Square Parking Authority",
    "Oakridge Library District",
    "City of Sunset Hills",
]
CONTRACTORS = [
    "Halloran Construction Inc.",
    "Apex Builders",
    "Bluewater Mechanical LLC",
    "Redwood Framing Co.",
    "Ironclad Restoration Inc.",
    "Summit Roofing & Sheet Metal",
    "Northstar Flooring Inc.",
    "Delta Electric Group",
]
WORK = [
    "Furnish and install additional fire-rated drywall at the Level 2 corridor per RFI-{n}.",
    "Replace deteriorated roof decking discovered after tear-off of the existing membrane.",
    "Relocate two floor drains to clear newly found post-tensioned cables.",
    "Credit for deleted bleacher railing finish upgrade per owner direction.",
    "Add two exterior hose bibs at the east wall per ASI-{n}.",
    "Substitute powder-coated railings approved by the owner in lieu of galvanized.",
    "Remove and dispose of unforeseen buried concrete footing at gridline C.",
]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    text: str
    truth: dict[str, Any]  # same shape as samples/expected/*.json "values"
    layout: str
    damaged: bool  # OCR-style damage was injected into a value


def money(value: Decimal, style: str) -> str:
    sign = value < 0
    body = f"{abs(value):,.2f}"
    if style == "paren" and sign:
        return f"(${body})"
    return f"-${body}" if sign else f"${body}"


def date_text(day: date, style: str) -> str:
    if style == "iso":
        return day.isoformat()
    if style == "named":
        return f"{MONTHS[day.month - 1]} {day.day}, {day.year}"
    if style == "dmy_named":
        return f"{day.day} {MONTHS[day.month - 1]} {day.year}"
    return f"{day.month:02d}/{day.day:02d}/{day.year}"  # numeric, month first; day > 12 below


def _damage(text: str, rng: random.Random) -> str:
    swaps = {"0": "O", "1": "l", "5": "S", "8": "B"}
    spots = [i for i, ch in enumerate(text) if ch in swaps]
    if not spots:
        return text
    i = rng.choice(spots)
    return text[:i] + swaps[text[i]] + text[i + 1 :]


Layout = Callable[[dict[str, str]], str]


def _standard(v: dict[str, str]) -> str:
    return "\n".join(
        [
            "CHANGE ORDER",
            f"Change Order No.: {v['no']}",
            f"Date: {v['date']}",
            f"Project: {v['project']}",
            f"Owner: {v['owner']}",
            f"Contractor: {v['contractor']}",
            "Description of Change:",
            v["description"],
            f"Contract Sum Prior to This Change Order: {v['before']}",
            f"Net Change by This Change Order: {v['amount']}",
            f"New Contract Sum Including This Change Order: {v['after']}",
            f"Schedule Impact: {v['days']}",
        ]
    )


def _alt_labels(v: dict[str, str]) -> str:
    return "\n".join(
        [
            "CONTRACT CHANGE ORDER",
            f"CO #  {v['no']}                    Dated: {v['date']}",
            f"Job: {v['project']}",
            f"Client: {v['owner']}",
            f"GC: {v['contractor']}",
            f"Scope: {v['description']}",
            f"Prior Contract Sum: {v['before']}",
            f"This Change Order Amount: {v['amount']}",
            f"Revised Contract Sum: {v['after']}",
            f"Time Extension: {v['days']}",
        ]
    )


def _header_table(v: dict[str, str]) -> str:
    return "\n".join(
        [
            "CHANGE ORDER SUMMARY",
            "",
            "| CO No. | Date Issued | Project | Contractor |",
            f"| {v['no']} | {v['date']} | {v['project']} | {v['contractor']} |",
            "",
            f"Owner: {v['owner']}",
            "",
            "Description of Change:",
            v["description"],
            "",
            "| Net Change | Previous Contract Sum | New Contract Sum |",
            f"| {v['amount']} | {v['before']} | {v['after']} |",
            "",
            f"Schedule Impact: {v['days']}",
        ]
    )


def _label_columns(v: dict[str, str]) -> str:
    return "\n".join(
        [
            "CHANGE ORDER",
            "",
            "Change Order No.",
            "Date",
            "Project",
            "Owner",
            "Contractor",
            "",
            v["no"],
            v["date"],
            v["project"],
            v["owner"],
            v["contractor"],
            "",
            "Description of Change:",
            v["description"],
            "",
            f"Net Change by This Change Order: {v['amount']}",
            f"Contract Sum Prior to This Change Order: {v['before']}",
            f"New Contract Sum Including This Change Order: {v['after']}",
            f"Schedule Impact: {v['days']}",
        ]
    )


LAYOUTS: dict[str, Layout] = {
    "standard": _standard,
    "alt_labels": _alt_labels,
    "header_table": _header_table,
    "label_columns": _label_columns,
}


def make_case(rng: random.Random, index: int) -> Case:
    before = Decimal(rng.randrange(150_000, 9_000_000, 500))
    amount = Decimal(rng.randrange(-60_000, 120_000, 50)) or Decimal(1_000)
    after = before + amount
    day = date(2025, 1, 1) + timedelta(days=rng.randrange(0, 700))
    if day.day <= 12:  # keep numeric dates unambiguous so truth is well defined
        day = day.replace(day=rng.randrange(13, 28))
    days = rng.choice([0, 0, 3, 5, 7, 10, 14, 21, 30])
    number = rng.choice([f"CO-{rng.randrange(1, 200):03d}", f"{rng.randrange(1, 60):02d}"])
    description = rng.choice(WORK).format(n=rng.randrange(10, 99))
    layout = rng.choice(sorted(LAYOUTS))
    date_style = rng.choice(["iso", "named", "dmy_named", "numeric"])
    money_style = rng.choice(["plain", "paren"])
    truth = {
        "change_order_number": number,
        "date": day.isoformat(),
        "project_name": rng.choice(PROJECTS),
        "owner": rng.choice(OWNERS),
        "contractor": rng.choice(CONTRACTORS),
        "description": description,
        "amount": f"{amount:.2f}",
        "contract_sum_before": f"{before:.2f}",
        "contract_sum_after": f"{after:.2f}",
        "schedule_impact_days": days,
    }
    values: dict[str, str] = {
        "no": number,
        "date": date_text(day, date_style),
        "project": str(truth["project_name"]),
        "owner": str(truth["owner"]),
        "contractor": str(truth["contractor"]),
        "description": description,
        "before": money(before, money_style),
        "amount": money(amount, money_style),
        "after": money(after, money_style),
        "days": f"{days} days" if days else rng.choice(["0 days", "None"]),
    }
    damaged = rng.random() < 0.15
    if damaged:
        key = rng.choice(["before", "amount", "after"])
        values[key] = _damage(values[key], rng)
    return Case(f"syn_{index:04d}", LAYOUTS[layout](values), truth, layout, damaged)


def make_corpus(n: int, seed: int = 7) -> list[Case]:
    rng = random.Random(seed)
    return [make_case(rng, i) for i in range(n)]


def write_corpus(cases: Sequence[Case], out_dir: Path) -> None:
    (out_dir / "expected").mkdir(parents=True, exist_ok=True)
    for case in cases:
        (out_dir / f"{case.name}.txt").write_text(case.text + "\n", encoding="utf-8")
        expected = {
            "source": f"{case.name}.txt",
            "needs_review": case.damaged,
            "rules_only_misses": [],
            "values": case.truth,
        }
        (out_dir / "expected" / f"{case.name}.json").write_text(
            json.dumps(expected, indent=2) + "\n", encoding="utf-8"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m co_extract.corpus")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    write_corpus(make_corpus(args.n, args.seed), args.out_dir)
    print(f"wrote {args.n} documents to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
