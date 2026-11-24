"""Bytecode benchmark runner and report generator.

Usage
-----
Run benchmark (outputs JSON):
    python scripts/benchmark.py --version base --output results-base.json
    python scripts/benchmark.py --version dev  --output results-dev.json

Merge two result files and render a report:
    python scripts/benchmark.py --merge results-base.json results-dev.json --format markdown

List scenario groups (for CI matrix):
    python scripts/benchmark.py --list-groups
"""

from __future__ import annotations

import json
import sys
import types
from abc import ABC, abstractmethod
from argparse import ArgumentParser
from dataclasses import dataclass
from math import floor, log
from pathlib import Path
from textwrap import wrap
from typing import Any, Callable

from scipy.stats import ttest_ind

VERSIONS = ("base", "dev")


# ---- Corpus ----------------------------------------------------------------


def _collect_code_objects(root: types.CodeType, depth: int = 0) -> list[types.CodeType]:
    result = [root]
    if depth > 0:
        for const in root.co_consts:
            if isinstance(const, types.CodeType):
                result.extend(_collect_code_objects(const, depth - 1))
    return result


def _dis_corpus() -> list[types.CodeType]:
    import importlib.util

    spec = importlib.util.find_spec("dis")
    assert spec and spec.origin
    top = compile(open(spec.origin).read(), spec.origin, "exec")
    return _collect_code_objects(top)


# ---- Scenario --------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """A single benchmark scenario.

    setup()        — called once before timing; return value is passed to bench.
    bench(fixture) — the unit of work to time; called in a tight loop.
    """

    group: str
    title: str
    setup: Callable[[], Any]
    bench: Callable[[Any], None]

    @property
    def group_slug(self) -> str:
        return self.group.lower().replace(" ", "-")


def _roundtrip_scenarios() -> list[Scenario]:
    from bytecode import Bytecode

    return [
        Scenario(
            group="Round-trip decompile/recompile",
            title=f"Round-trip [{co.co_name}]",
            setup=lambda co=co: co,
            bench=lambda co: Bytecode.from_code(co).to_code(),
        )
        for co in _dis_corpus()
    ]


# SCENARIOS is built lazily so that importing this module does not require
# bytecode to be installed (e.g. when running --list-groups or --merge only).
_SCENARIOS: list[Scenario] | None = None


def get_scenarios() -> list[Scenario]:
    global _SCENARIOS
    if _SCENARIOS is None:
        _SCENARIOS = [
            *_roundtrip_scenarios(),
            # Add new scenario groups here.
        ]
    return _SCENARIOS


def scenario_groups() -> list[str]:
    return list(dict.fromkeys(s.group for s in get_scenarios()))


# ---- Outcome ---------------------------------------------------------------


class Outcome:
    __critical_p__ = 0.025

    def __init__(self, data: list[float]) -> None:
        self.data = data
        self.mean = sum(data) / len(data)
        self.stdev = (
            (sum((v - self.mean) ** 2 for v in data) / (len(data) - 1)) ** 0.5
            if len(data) > 1
            else 0.0
        )

    def __repr__(self) -> str:
        n = -floor(log(self.stdev, 10)) if self.stdev else 0
        rmean = round(self.mean, n)
        rstdev = round(self.stdev, n)
        if n <= 0:
            rmean = int(rmean)
            rstdev = int(rstdev)
        return f"{rmean} ± {rstdev}"

    __str__ = __repr__

    def significant_vs(self, other: "Outcome") -> bool:
        _, p = ttest_ind(self.data, other.data, equal_var=False)
        return p < self.__critical_p__

    def is_better_than(self, other: "Outcome") -> bool:
        return self.mean > other.mean


# ---- Runner ----------------------------------------------------------------


def run_benchmark(
    n_runs: int,
    duration_s: float,
    filter_re: str | None = None,
) -> list[dict]:
    import re
    from time import perf_counter_ns as ns

    end_ns = int(duration_s * 1e9)
    pat = re.compile(filter_re) if filter_re else None

    records: list[dict] = []
    for scenario in get_scenarios():
        if pat and not pat.search(scenario.title):
            continue
        print(f"  {scenario.title} ...", file=sys.stderr)
        fixture = scenario.setup()
        samples: list[float] = []
        for _ in range(n_runs):
            deadline = ns() + end_ns
            count = 0
            while ns() < deadline:
                count += 1
                scenario.bench(fixture)
            samples.append(count / duration_s)
        records.append(
            {"group": scenario.group, "title": scenario.title, "samples": samples}
        )

    return records


# ---- JSON (de)serialisation ------------------------------------------------


def to_json(version: str, records: list[dict]) -> str:
    return json.dumps({"version": version, "results": records}, indent=2)


def from_json(path: Path) -> tuple[str, list[dict]]:
    doc = json.loads(path.read_text())
    return doc["version"], doc["results"]


# ---- Report ----------------------------------------------------------------


class Renderer(ABC):
    BETTER = "better"
    WORSE = "worse"
    SAME = "same"

    @abstractmethod
    def header(self, title: str, level: int = 1) -> None: ...

    @abstractmethod
    def paragraph(self, text: str) -> None: ...

    @abstractmethod
    def table(self, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None: ...

    def open_group(self, label: str) -> None:
        self.header(label, level=2)

    def close_group(self) -> None:
        return  # subclasses that need a closing delimiter override this


class TerminalRenderer(Renderer):
    def header(self, title: str, level: int = 1) -> None:
        print(title)
        print({1: "=", 2: "-"}.get(level, "~") * len(title))
        print()

    def paragraph(self, text: str) -> None:
        for line in wrap(text):
            print(line)
        print()

    def table(self, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
        col_widths = [
            max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)
        ]
        print("  ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)))
        print("  ".join("-" * w for w in col_widths))
        for row in rows:
            print("  ".join(f"{v:<{w}}" for v, w in zip(row, col_widths)))
        print()


class MarkdownRenderer(Renderer):
    BETTER = ":green_circle:"
    WORSE = ":red_circle:"
    SAME = ":yellow_circle:"

    def header(self, title: str, level: int = 1) -> None:
        print(f"{'#' * level} {title}")
        print()

    def paragraph(self, text: str) -> None:
        print(text)
        print()

    def table(self, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
        print("| " + " | ".join(headers) + " |")
        print(
            "| "
            + " | ".join(":---" if i == 0 else "---:" for i in range(len(headers)))
            + " |"
        )
        for row in rows:
            print("| " + " | ".join(row) + " |")
        print()

    def open_group(self, label: str) -> None:
        print("<details>")
        print(f"<summary><strong>{label}</strong></summary>")
        print()

    def close_group(self) -> None:
        print("</details>")
        print()


# ---- Rendering logic -------------------------------------------------------


def _compare_records(
    base_records: list[dict],
    dev_records: list[dict],
) -> dict[str, tuple[Outcome, Outcome]]:
    base_map = {r["title"]: Outcome(r["samples"]) for r in base_records}
    dev_map = {r["title"]: Outcome(r["samples"]) for r in dev_records}
    return {
        title: (base_map[title], dev_map[title])
        for title in base_map
        if title in dev_map
    }


def render_report(
    base_records: list[dict],
    dev_records: list[dict],
    renderer: Renderer,
) -> None:
    renderer.header("Bytecode Benchmarks")
    renderer.paragraph("Throughput comparison (iterations/s) — **dev** vs **base**.")

    pairs = _compare_records(base_records, dev_records)

    # Group by scenario group, preserving order from base_records.
    groups: dict[str, list[str]] = {}
    for r in base_records:
        if r["title"] in pairs:
            groups.setdefault(r["group"], []).append(r["title"])

    total_better = total_worse = total_same = 0

    for group_label, titles in groups.items():
        renderer.open_group(group_label)

        rows: list[tuple[str, ...]] = []
        n_better = n_worse = n_same = 0

        for title in titles:
            b, d = pairs[title]
            sig = d.significant_vs(b)
            if sig:
                if d.is_better_than(b):
                    delta = renderer.BETTER
                    n_better += 1
                else:
                    delta = renderer.WORSE
                    n_worse += 1
            else:
                delta = renderer.SAME
                n_same += 1
            rows.append((title, str(b), str(d), delta))

        renderer.table(("Scenario", "base (it/s)", "dev (it/s)", "Δ"), rows)

        total = n_better + n_worse + n_same
        renderer.paragraph(
            f"{n_better}/{total} better {renderer.BETTER}, "
            f"{n_worse}/{total} worse {renderer.WORSE}, "
            f"{n_same}/{total} no significant difference {renderer.SAME}."
        )

        renderer.close_group()
        total_better += n_better
        total_worse += n_worse
        total_same += n_same

    if len(groups) > 1:
        total = total_better + total_worse + total_same
        renderer.header("Overall summary", level=2)
        renderer.paragraph(
            f"{total_better}/{total} better {renderer.BETTER}, "
            f"{total_worse}/{total} worse {renderer.WORSE}, "
            f"{total_same}/{total} no significant difference {renderer.SAME}."
        )


# ---- CLI -------------------------------------------------------------------


def main() -> None:
    argp = ArgumentParser(description=__doc__)
    argp.add_argument(
        "--version", choices=VERSIONS, help="Label for this run's JSON output"
    )
    argp.add_argument("--output", type=Path, help="Write JSON results to FILE")
    argp.add_argument(
        "-n", type=int, default=5, help="Repetitions per scenario (default: 5)"
    )
    argp.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="Measurement window in seconds per repetition (default: 1.0)",
    )
    argp.add_argument("-k", metavar="REGEX", help="Only run scenarios matching REGEX")
    argp.add_argument(
        "--merge",
        nargs=2,
        metavar="FILE",
        help="Merge two JSON result files (base then dev) and render a report",
    )
    argp.add_argument(
        "--format",
        choices=["terminal", "markdown"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    argp.add_argument(
        "--pvalue",
        type=float,
        default=0.025,
        help="Significance threshold (default: 0.025)",
    )
    argp.add_argument(
        "--list-groups",
        action="store_true",
        help="Print scenario groups as a GitHub Actions matrix JSON and exit",
    )
    opts = argp.parse_args()

    Outcome.__critical_p__ = opts.pvalue

    if opts.list_groups:
        groups = scenario_groups()
        matrix = [{"name": g.lower().replace(" ", "-"), "filter": g} for g in groups]
        print(json.dumps({"include": matrix}))
        return

    if opts.merge:
        _, base_records = from_json(Path(opts.merge[0]))
        _, dev_records = from_json(Path(opts.merge[1]))
        renderer: Renderer = (
            MarkdownRenderer() if opts.format == "markdown" else TerminalRenderer()
        )
        render_report(base_records, dev_records, renderer)
        return

    if not opts.version:
        argp.error("--version is required when not using --merge or --list-groups")

    print(f"Running benchmarks (version={opts.version}) ...", file=sys.stderr)
    records = run_benchmark(opts.n, opts.duration, filter_re=opts.k)
    output = to_json(opts.version, records)

    if opts.output:
        opts.output.write_text(output)
        print(f"Results written to {opts.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
