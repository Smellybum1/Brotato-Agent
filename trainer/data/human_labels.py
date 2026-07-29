"""Human keyboard-vector label extraction for the human-labelled BC dataset.

Mod 0.2.56 logs the human player's real input vector at capture path
``payload.teacher.contributions.human`` = ``{x, y, samples, all_identical}``.
Builds before 0.2.56 have NO such block: ``teacher.action`` recorded the
AGENT's intent even during a human-driven run, so those runs cannot contribute
human labels at all.

This module is deliberately tiny and pure so the filter semantics are unit
testable without touching the runs directory:

  * :func:`extract_human_label` — pull the block, or report why it is unusable;
  * :data:`DROP_NO_BLOCK` / :data:`DROP_NO_SAMPLES` — the two drop reasons.

Filter policy (fixed here, mirrored by the builder and the loader):

  * no ``human`` block at all      -> DROP  (pre-0.2.56 capture)
  * ``samples == 0``               -> DROP  (no input sampled in the interval;
                                            no label exists to clone)
  * ``all_identical == false``     -> KEEP, flag recorded per row so training
                                            can ablate on it (~15% of rows)
  * ``(x, y) == (0, 0)``           -> KEEP  (standing still is a real action)

The temporal-validity filter is NOT applied here; it is the encoder's
``valid & temporal_valid`` conjunction, applied by the loader exactly as the
teacher-labelled loader does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


DROP_NO_BLOCK = "no_human_block"
DROP_NO_SAMPLES = "zero_samples"

CAPTURE_PATH = ("teacher", "contributions", "human")


class HumanLabelError(ValueError):
    """Raised when a ``human`` block is present but structurally unusable."""


@dataclass(frozen=True)
class HumanLabel:
    """One usable human label: the keyboard vector plus its provenance flags."""

    x: float
    y: float
    samples: int
    all_identical: bool

    @property
    def is_zero(self) -> bool:
        return self.x == 0.0 and self.y == 0.0


def get_human_block(payload: dict) -> dict | None:
    """Return ``payload.teacher.contributions.human`` if it is a mapping, else None."""
    node: object = payload
    for key in CAPTURE_PATH:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node if isinstance(node, dict) else None


def extract_human_label(payload: dict) -> tuple[HumanLabel | None, str | None]:
    """Extract the human label from a capture payload.

    Returns ``(label, None)`` when the row is keepable, or ``(None, reason)``
    with reason one of :data:`DROP_NO_BLOCK` / :data:`DROP_NO_SAMPLES`.

    Hard-errors (``HumanLabelError``) on a present-but-malformed block: a
    non-numeric or non-finite component is a mod bug, not a row to skip
    silently.
    """
    block = get_human_block(payload)
    if block is None:
        return None, DROP_NO_BLOCK

    try:
        samples = int(block.get("samples", 0))
    except (TypeError, ValueError) as exc:
        raise HumanLabelError(f"human.samples is not an integer: {block.get('samples')!r}") from exc
    if samples < 0:
        raise HumanLabelError(f"human.samples is negative: {samples}")
    if samples == 0:
        return None, DROP_NO_SAMPLES

    try:
        x = float(block["x"])
        y = float(block["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HumanLabelError(f"human block missing finite x/y: {block!r}") from exc
    if not (math.isfinite(x) and math.isfinite(y)):
        raise HumanLabelError(f"human block has non-finite x/y: {block!r}")

    raw_flag = block.get("all_identical", True)
    if not isinstance(raw_flag, bool):
        raise HumanLabelError(f"human.all_identical is not a bool: {raw_flag!r}")

    return HumanLabel(x=x, y=y, samples=samples, all_identical=raw_flag), None
