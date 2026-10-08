"""Export preview: what the harmonized CSV changes relative to the upload.

Columns are aligned through the export's own provenance (source → export
column), so renames are known rather than guessed, and rows keep their order.
Each changed cell is attributed to an ontology rewrite or a spreadsheet escape.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.services.exporter import HarmonizedTable

# Every ontology rewrite is listed: each is a confirmed term a curator may want
# to check. Other changes (spreadsheet escapes, one per distinct cell text) are
# listed up to this many per column; the rest are only counted.
MAX_VALUE_CHANGES = 25


class UnknownColumnError(ValueError):
    """The requested column is not part of the harmonized export."""


def build_preview(
    study_id: str,
    raw_text: pd.DataFrame,
    table: HarmonizedTable,
    *,
    offset: int = 0,
    limit: int = 50,
    changed_only: bool = False,
    column: str | None = None,
) -> dict[str, Any]:
    """Compare ``table`` with the upload's original text.

    ``changed_only`` keeps rows with at least one changed cell (in ``column``
    when given); ``offset``/``limit`` select a page of those rows.
    """
    targets = list(table.frame.columns)
    if column is not None and column not in targets:
        raise UnknownColumnError(f"'{column}' is not a column of the harmonized export.")

    source_of = {p.target: p.source for p in table.plan if p.target is not None}
    position = {target: j for j, target in enumerate(targets)}
    n_rows = len(table.frame.index)

    # (row, export column) grids: uploaded text, exported text, and why they differ.
    before = raw_text[[source_of[t] for t in targets]].to_numpy(dtype=object)
    after = table.frame.to_numpy(dtype=object)
    changed = before != after
    reasons = np.where(
        table.rewritten.to_numpy(dtype=bool),
        "ontology",
        np.where(table.escaped.to_numpy(dtype=bool), "escaped", "other"),
    )

    changed_per_column = changed.sum(axis=0)
    value_changes, more_value_changes = _value_changes(before, after, reasons, changed)
    columns = []
    for plan in table.plan:
        j = position.get(plan.target) if plan.target is not None else None
        columns.append(
            {
                "source": plan.source,
                "target": plan.target,
                "action": plan.action,
                "mapping_status": plan.mapping_status,
                "drop_reason": plan.drop_reason,
                "conflicts_with": plan.conflicts_with,
                "changed_cells": int(changed_per_column[j]) if j is not None else 0,
                "value_changes": value_changes.get(j, []) if j is not None else [],
                "more_value_changes": more_value_changes.get(j, 0) if j is not None else 0,
            }
        )

    changed_rows = changed.any(axis=1)
    actions = [p.action for p in table.plan]
    summary = {
        "rows": n_rows,
        "columns_before": len(raw_text.columns),
        "columns_after": len(targets),
        "renamed": actions.count("renamed"),
        "matched": actions.count("matched"),
        "kept": actions.count("kept"),
        "dropped": actions.count("dropped"),
        "pending": sum(
            1 for p in table.plan if p.target is not None and p.mapping_status == "pending"
        ),
        "changed_cells": int(changed.sum()),
        "changed_rows": int(changed_rows.sum()),
        "compared_cells": n_rows * len(targets),
    }

    if changed_only:
        selected = changed[:, position[column]] if column is not None else changed_rows
        positions = np.flatnonzero(selected)
    else:
        positions = np.arange(n_rows)

    items = [
        {
            "line": int(pos) + 1,
            "values": [str(v) for v in after[pos]],
            "changes": [
                {"column": int(j), "before": str(before[pos, j]), "reason": str(reasons[pos, j])}
                for j in np.flatnonzero(changed[pos])
            ],
        }
        for pos in positions[offset : offset + limit]
    ]

    return {
        "study_id": study_id,
        "summary": summary,
        "columns": columns,
        "rows": {
            "total": len(positions),
            "offset": offset,
            "limit": limit,
            "columns": targets,
            "items": items,
        },
    }


def _value_changes(
    before: np.ndarray, after: np.ndarray, reasons: np.ndarray, changed: np.ndarray
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, int]]:
    """Distinct before → after pairs per export column, most frequent first.

    Returns the listed pairs (every ontology rewrite, plus up to
    ``MAX_VALUE_CHANGES`` other changes per column) and how many other pairs
    each column leaves unlisted, both keyed by column position.
    """
    rows, cols = np.nonzero(changed)
    if len(rows) == 0:
        return {}, {}
    cells = pd.DataFrame(
        {
            "col": cols,
            "before": before[rows, cols],
            "after": after[rows, cols],
            "reason": reasons[rows, cols],
        }
    )
    counts = (
        cells.groupby(["col", "before", "after", "reason"], sort=False, dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(
            ["col", "count", "before", "after"],
            ascending=[True, False, True, True],
            kind="stable",
        )
    )
    capped = counts["reason"] != "ontology"
    rank = counts[capped].groupby("col", sort=False).cumcount().reindex(counts.index)
    listed: dict[int, list[dict[str, Any]]] = {}
    for col, b, a, reason, count in counts[~capped | (rank < MAX_VALUE_CHANGES)][
        ["col", "before", "after", "reason", "count"]
    ].itertuples(index=False, name=None):
        listed.setdefault(int(col), []).append(
            {"before": str(b), "after": str(a), "count": int(count), "reason": str(reason)}
        )
    distinct = counts[capped].groupby("col", sort=False).size()
    more = {int(col): max(0, int(n) - MAX_VALUE_CHANGES) for col, n in distinct.items()}
    return listed, more
