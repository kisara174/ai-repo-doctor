"""Pure scoring math for repeated diagnosis runs."""


_COUNT_KEYS = frozenset(
    {
        "accepted_tp",
        "accepted_fp",
        "uncertain",
        "duplicate",
        "accepted_count",
        "rejected_count",
        "detected_known_bug_cases",
        "successful_bug_cases",
        "all_requested_bug_cases",
        "successful_control_cases_with_accepted_fp",
        "successful_fixed_and_control_cases",
        "failed_calls",
        "rejected_true_positive",
    }
)


def calculate_repeat_metrics(counts: dict[str, int]) -> dict:
    if not isinstance(counts, dict) or set(counts) != _COUNT_KEYS:
        raise ValueError("counts must contain exactly the required count keys")

    for name, value in counts.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")

    accepted_tp = counts["accepted_tp"]
    accepted_fp = counts["accepted_fp"]
    accepted_count = counts["accepted_count"]
    rejected_count = counts["rejected_count"]
    total_findings = accepted_count + rejected_count

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    metrics = {
        "precision": ratio(accepted_tp, accepted_tp + accepted_fp),
        "recall": ratio(
            counts["detected_known_bug_cases"], counts["successful_bug_cases"]
        ),
        "end_to_end_detection": ratio(
            counts["detected_known_bug_cases"], counts["all_requested_bug_cases"]
        ),
        "grounding_rate": ratio(accepted_count, total_findings),
        "control_false_alarm_rate": ratio(
            counts["successful_control_cases_with_accepted_fp"],
            counts["successful_fixed_and_control_cases"],
        ),
        "uncertain_rate": ratio(counts["uncertain"], total_findings),
        "duplicate_rate": ratio(counts["duplicate"], total_findings),
    }
    return {"counts": dict(counts), "metrics": metrics}
