from dataclasses import dataclass
from unittest.mock import MagicMock

from plex_audit.context import FindingsSink, ScanContext
from plex_audit.engine import Engine
from plex_audit.types import Category, Finding, Severity


@dataclass
class _FakeCheck:
    id: str = "fake"
    name: str = "Fake Check"
    category: Category = Category.METADATA
    parallel_safe: bool = True
    requires_filesystem: bool = False
    findings: tuple[Finding, ...] = ()
    raises: Exception | None = None

    def run(self, ctx: ScanContext):
        if self.raises:
            raise self.raises
        for f in self.findings:
            yield f


def _ctx(filesystem: bool = True) -> ScanContext:
    return ScanContext(
        plex=MagicMock(),
        path_mapper=MagicMock(has_mappings=filesystem),
        config=MagicMock(),
        filesystem_available=filesystem,
        _sink=FindingsSink(),
    )


def test_engine_runs_all_enabled_checks_and_collects_findings():
    f1 = Finding(check_id="a", severity=Severity.WARN, title="t", subject="s1")
    f2 = Finding(check_id="b", severity=Severity.INFO, title="t", subject="s2")
    ctx = _ctx()
    engine = Engine(checks=[_FakeCheck(id="a", findings=(f1,)), _FakeCheck(id="b", findings=(f2,))])
    engine.run(ctx, enabled="all", disabled=[])
    assert {f.check_id for f in ctx._sink.all()} == {"a", "b"}


def test_engine_respects_enabled_list():
    ctx = _ctx()
    engine = Engine(checks=[
        _FakeCheck(id="a", findings=(Finding(check_id="a", severity=Severity.WARN, title="t", subject="s"),)),
        _FakeCheck(id="b", findings=(Finding(check_id="b", severity=Severity.WARN, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled=["a"], disabled=[])
    assert {f.check_id for f in ctx._sink.all()} == {"a"}


def test_engine_respects_disabled_list():
    ctx = _ctx()
    engine = Engine(checks=[
        _FakeCheck(id="a", findings=(Finding(check_id="a", severity=Severity.WARN, title="t", subject="s"),)),
        _FakeCheck(id="b", findings=(Finding(check_id="b", severity=Severity.WARN, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled="all", disabled=["b"])
    assert {f.check_id for f in ctx._sink.all()} == {"a"}


def test_engine_isolates_crashing_check():
    ctx = _ctx()
    engine = Engine(checks=[
        _FakeCheck(id="bad", raises=RuntimeError("boom")),
        _FakeCheck(id="good", findings=(Finding(check_id="good", severity=Severity.INFO, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled="all", disabled=[])
    findings = ctx._sink.all()
    assert any(f.check_id == "engine" and f.severity == Severity.ERROR and "bad" in f.subject for f in findings)
    assert any(f.check_id == "good" for f in findings)


def test_engine_skips_filesystem_checks_when_unavailable():
    ctx = _ctx(filesystem=False)
    engine = Engine(checks=[
        _FakeCheck(id="fs", requires_filesystem=True,
                   findings=(Finding(check_id="fs", severity=Severity.WARN, title="t", subject="s"),)),
    ])
    engine.run(ctx, enabled="all", disabled=[])
    findings = ctx._sink.all()
    assert not any(f.check_id == "fs" and f.severity == Severity.WARN for f in findings)
    assert any(f.check_id == "engine" and f.severity == Severity.INFO and "fs" in f.subject for f in findings)
