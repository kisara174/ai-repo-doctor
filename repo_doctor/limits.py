"""Per-analysis resource boundaries; deadlines are cooperative, not process isolation."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import math
import time
from collections.abc import Callable


class AnalysisLimitError(ValueError):
    """A whole-query resource failure, never a per-file parse error."""


@dataclass(frozen=True, slots=True)
class AnalysisLimits:
    max_file_bytes: int = 2 * 1024 * 1024
    max_total_bytes: int = 64 * 1024 * 1024
    max_files: int = 5000
    git_timeout_seconds: float = 15
    index_timeout_seconds: float = 60

    def __post_init__(self):
        for name in ('max_file_bytes', 'max_total_bytes', 'max_files'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('git_timeout_seconds', 'index_timeout_seconds'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be positive and finite')

    def as_dict(self) -> dict:
        return {**asdict(self), 'timeout_kind': 'cooperative'}


class AnalysisBudget:
    def __init__(self, limits: AnalysisLimits | None = None, *, clock: Callable[[], float] | None = None):
        self.limits = limits if limits is not None else AnalysisLimits()
        self._clock = clock if clock is not None else time.monotonic
        self._started = self._clock()
        self.read_bytes = 0

    def checkpoint(self, phase: str) -> None:
        if self._clock() - self._started > self.limits.index_timeout_seconds:
            raise AnalysisLimitError(
                f'index_timeout_seconds limit {self.limits.index_timeout_seconds} exceeded '
                f'at {phase} (cooperative checkpoint; native parsing is not interrupted)')

    @contextmanager
    def exclude_external_wait(self):
        """Legacy provider wait has its own timeout; never run source work here."""
        self.checkpoint('before external wait')
        started = self._clock()
        try:
            yield
        finally:
            self._started += self._clock() - started

    def check_file_count(self, count: int) -> None:
        if count > self.limits.max_files:
            raise AnalysisLimitError(f'max_files limit {self.limits.max_files} exceeded: {count} selected files')

    def read_size(self) -> int:
        """At most one overflow byte, even when a file grows after stat."""
        return min(self.limits.max_file_bytes, self.limits.max_total_bytes - self.read_bytes) + 1

    def record_read(self, size: int, path: str) -> None:
        if size > self.limits.max_file_bytes:
            raise AnalysisLimitError(f'max_file_bytes limit {self.limits.max_file_bytes} exceeded: {path}')
        if self.read_bytes + size > self.limits.max_total_bytes:
            raise AnalysisLimitError(f'max_total_bytes limit {self.limits.max_total_bytes} exceeded: {path}')
        self.read_bytes += size
