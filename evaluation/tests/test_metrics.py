from evaluation.evaluator import CaseResult, EventComparison, Verdict
from evaluation.metrics import compute_metrics


def comparison(verdict: Verdict, expected=object(), generated=object()) -> EventComparison:
    return EventComparison(
        verdict=verdict,
        expected=expected if verdict != Verdict.UNSUPPORTED else None,
        generated=generated if verdict != Verdict.MISSING else None,
        field_results=[],
    )


class TestComputeMetrics:
    def test_all_correct_yields_perfect_scores(self):
        results = [CaseResult("c1", [comparison(Verdict.CORRECT)])]
        metrics = compute_metrics(results)
        assert metrics.event_precision == 1.0
        assert metrics.event_recall == 1.0
        assert metrics.unsupported_event_rate == 0.0

    def test_all_missing_yields_zero_recall(self):
        results = [CaseResult("c1", [comparison(Verdict.MISSING)])]
        metrics = compute_metrics(results)
        assert metrics.event_recall == 0.0
        # No generated events at all, so precision is undefined, not zero.
        assert metrics.event_precision is None

    def test_all_unsupported_yields_zero_precision_and_full_unsupported_rate(self):
        results = [CaseResult("c1", [comparison(Verdict.UNSUPPORTED)])]
        metrics = compute_metrics(results)
        assert metrics.event_precision == 0.0
        assert metrics.unsupported_event_rate == 1.0

    def test_no_cases_yields_none_metrics_not_crash(self):
        metrics = compute_metrics([])
        assert metrics.case_count == 0
        assert metrics.event_precision is None
        assert metrics.event_recall is None

    def test_mixed_verdicts_counted_correctly(self):
        results = [
            CaseResult(
                "c1",
                [
                    comparison(Verdict.CORRECT),
                    comparison(Verdict.PARTIAL),
                    comparison(Verdict.UNSUPPORTED),
                    comparison(Verdict.MISSING),
                    comparison(Verdict.CONTRADICTORY),
                ],
            )
        ]
        metrics = compute_metrics(results)
        assert metrics.correct_count == 1
        assert metrics.partial_count == 1
        assert metrics.unsupported_count == 1
        assert metrics.missing_count == 1
        assert metrics.contradictory_count == 1
        # tp=2 (correct+partial), fp=2 (unsupported+contradictory), fn=1 (missing)
        assert metrics.event_precision == 0.5
        assert metrics.event_recall == 2 / 3
