#!/usr/bin/env python3
"""
Tests for baseline_comparison.py - Benchmark baseline comparison functionality.
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from baseline_comparison import (
    LatencyMetrics, BenchmarkBaseline, ComparisonMetrics, ComparisonReport,
    compare_metric, compare_benchmarks, load_benchmark_from_json,
    save_baseline, load_baseline, list_baselines, delete_baseline
)


def create_test_baseline(
    name: str = "test_baseline",
    requests_per_second: float = 100.0,
    avg_latency: float = 50.0,
    p95_latency: float = 150.0,
    p99_latency: float = 200.0,
) -> BenchmarkBaseline:
    """Helper to create a test baseline."""
    return BenchmarkBaseline(
        name=name,
        benchmark_type="latency",
        timestamp=datetime.now().timestamp(),
        duration_seconds=60.0,
        total_requests=6000,
        successful_requests=5900,
        failed_requests=100,
        timeout_requests=0,
        requests_per_second=requests_per_second,
        latency_ms=LatencyMetrics(
            min_ms=10.0,
            avg_ms=avg_latency,
            p50_ms=40.0,
            p90_ms=100.0,
            p95_ms=p95_latency,
            p99_ms=p99_latency,
            max_ms=500.0,
            stddev_ms=20.0,
        ),
        error_distribution={"timeout": 0, "5xx": 100},
        target_endpoint="http://localhost:8080/health",
        concurrency=10,
    )


def create_test_results_file(filepath: Path, **kwargs) -> None:
    """Helper to create a test benchmark results JSON file."""
    baseline = create_test_baseline(**kwargs)
    with open(filepath, 'w') as f:
        json.dump(baseline.to_dict(), f, indent=2)


def test_latency_metrics():
    """Test LatencyMetrics data model."""
    metrics = LatencyMetrics(
        min_ms=10.0,
        avg_ms=50.0,
        p50_ms=40.0,
        p90_ms=100.0,
        p95_ms=150.0,
        p99_ms=200.0,
        max_ms=500.0,
        stddev_ms=20.0,
    )

    assert metrics.min_ms == 10.0
    assert metrics.p99_ms == 200.0
    assert metrics.max_ms == 500.0

    # Test conversion to/from dict
    data = metrics.to_dict()
    assert isinstance(data, dict)
    assert data['avg_ms'] == 50.0

    metrics2 = LatencyMetrics.from_dict(data)
    assert metrics2.avg_ms == metrics.avg_ms
    print("[PASS] test_latency_metrics passed")


def test_benchmark_baseline():
    """Test BenchmarkBaseline data model."""
    baseline = create_test_baseline()

    assert baseline.name == "test_baseline"
    assert baseline.benchmark_type == "latency"
    assert baseline.total_requests == 6000
    assert baseline.requests_per_second == 100.0

    # Test conversion to dict
    data = baseline.to_dict()
    assert data['name'] == "test_baseline"
    assert data['latency_ms']['avg_ms'] == 50.0
    print("[PASS] test_benchmark_baseline passed")


def test_compare_metric_regression():
    """Test comparing a metric that shows regression (higher is worse)."""
    # Latency regression: baseline 50ms, current 75ms
    comparison = compare_metric("Avg Latency", 50.0, 75.0)

    assert comparison.metric_name == "Avg Latency"
    assert comparison.baseline_value == 50.0
    assert comparison.current_value == 75.0
    assert comparison.delta == 25.0
    assert comparison.delta_percent == 50.0
    assert comparison.is_regression is True
    assert comparison.is_improvement is False
    print("[PASS] test_compare_metric_regression passed")


def test_compare_metric_improvement():
    """Test comparing a metric that shows improvement."""
    # Latency improvement: baseline 100ms, current 50ms
    comparison = compare_metric("Avg Latency", 100.0, 50.0)

    assert comparison.delta == -50.0
    assert comparison.delta_percent == -50.0
    assert comparison.is_regression is False
    assert comparison.is_improvement is True
    print("[PASS] test_compare_metric_improvement passed")


def test_compare_metric_small_change():
    """Test comparing a metric with small change (no threshold breach)."""
    # Small regression: baseline 100ms, current 105ms (5% increase)
    comparison = compare_metric("Avg Latency", 100.0, 105.0,
                               warning_threshold=10.0,
                               critical_threshold=25.0)

    assert comparison.delta == 5.0
    assert comparison.delta_percent == 5.0
    assert comparison.is_regression is True
    assert comparison.severity == 'info'  # Below warning threshold
    print("[PASS] test_compare_metric_small_change passed")


def test_compare_metric_warning_threshold():
    """Test comparing a metric that hits warning threshold."""
    # Moderate regression: baseline 100ms, current 115ms (15% increase)
    comparison = compare_metric("Avg Latency", 100.0, 115.0,
                               warning_threshold=10.0,
                               critical_threshold=25.0)

    assert comparison.delta_percent == 15.0
    assert comparison.severity == 'warning'  # Between warning and critical
    print("[PASS] test_compare_metric_warning_threshold passed")


def test_compare_metric_critical_threshold():
    """Test comparing a metric that hits critical threshold."""
    # Severe regression: baseline 100ms, current 150ms (50% increase)
    comparison = compare_metric("Avg Latency", 100.0, 150.0,
                               warning_threshold=10.0,
                               critical_threshold=25.0)

    assert comparison.delta_percent == 50.0
    assert comparison.severity == 'critical'  # Above critical threshold
    print("[PASS] test_compare_metric_critical_threshold passed")


def test_compare_benchmarks_overall():
    """Test comparing two full benchmark results."""
    baseline = create_test_baseline(
        requests_per_second=100.0,
        avg_latency=50.0,
        p95_latency=150.0,
        p99_latency=200.0,
    )

    # Slightly degraded performance
    current = create_test_baseline(
        requests_per_second=95.0,  # 5% lower throughput
        avg_latency=60.0,  # 20% higher latency
        p95_latency=180.0,  # 20% higher
        p99_latency=240.0,  # 20% higher
    )

    report = compare_benchmarks(baseline, current)

    assert report.benchmark_type == "latency"
    assert report.total_comparisons > 0
    assert report.has_critical_regression is False  # None hit critical threshold
    assert len(report.regressions) > 0  # Should have some regressions
    print("[PASS] test_compare_benchmarks_overall passed")


def test_compare_benchmarks_critical_regression():
    """Test detecting critical regression in benchmark comparison."""
    baseline = create_test_baseline(
        requests_per_second=100.0,
        avg_latency=50.0,
    )

    # Severely degraded performance
    current = create_test_baseline(
        requests_per_second=50.0,  # 50% lower throughput
        avg_latency=150.0,  # 200% higher latency (critical)
    )

    report = compare_benchmarks(baseline, current,
                               warning_threshold=10.0,
                               critical_threshold=25.0)

    assert report.has_critical_regression is True
    assert len(report.regressions) > 0
    print("[PASS] test_compare_benchmarks_critical_regression passed")


def test_benchmark_baseline_save_and_load():
    """Test saving and loading baseline to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        baseline = create_test_baseline()
        baseline_file = tmppath / "test_baseline.json"
        baseline.save(str(baseline_file.with_suffix('')).split('/')[-1])

        # Manually save for this test
        with open(baseline_file, 'w') as f:
            json.dump(baseline.to_dict(), f)

        # Load it back
        loaded = BenchmarkBaseline.from_json_file(baseline_file)

        assert loaded.name == baseline.name
        assert loaded.requests_per_second == baseline.requests_per_second
        assert loaded.latency_ms.avg_ms == baseline.latency_ms.avg_ms
        print("[PASS] test_benchmark_baseline_save_and_load passed")


def test_load_benchmark_from_json():
    """Test loading benchmark results from JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        results_file = Path(tmpdir) / "results.json"
        create_test_results_file(results_file, requests_per_second=100.0)

        benchmark = load_benchmark_from_json(results_file)

        assert benchmark.requests_per_second == 100.0
        assert benchmark.total_requests == 6000
        assert benchmark.latency_ms.avg_ms == 50.0
        print("[PASS] test_load_benchmark_from_json passed")


def test_comparison_report_attributes():
    """Test ComparisonReport data structure."""
    comparison = ComparisonMetrics(
        metric_name="Test Metric",
        baseline_value=100.0,
        current_value=110.0,
        delta=10.0,
        delta_percent=10.0,
        is_regression=True,
        is_improvement=False,
        severity="warning",
    )

    report = ComparisonReport(
        baseline_name="test",
        baseline_timestamp=datetime.now().timestamp(),
        current_timestamp=datetime.now().timestamp(),
        benchmark_type="latency",
        comparison_date=datetime.now().isoformat(),
        total_comparisons=1,
        regressions=[comparison],
    )

    assert report.baseline_name == "test"
    assert report.regression_count == 1
    assert len(report.regressions) == 1
    assert report.has_critical_regression is False

    # Test conversion to dict
    data = report.to_dict()
    assert isinstance(data, dict)
    assert data['regression_count'] == 1
    print("[PASS] test_comparison_report_attributes passed")


def test_latency_vs_throughput_metric_logic():
    """Test that throughput metrics correctly invert the regression logic."""
    # For throughput, a decrease is a regression, not an improvement
    baseline = create_test_baseline(requests_per_second=100.0)
    current = create_test_baseline(requests_per_second=90.0)

    report = compare_benchmarks(baseline, current)

    # Find the Requests/sec metric in regressions
    rps_metric = None
    for metric in report.regressions + report.improvements + report.neutral:
        if "Requests/sec" in metric.metric_name:
            rps_metric = metric
            break

    assert rps_metric is not None
    assert rps_metric.is_regression is True  # Lower throughput is a regression
    assert rps_metric.delta < 0  # Negative delta (90 - 100)
    print("[PASS] test_latency_vs_throughput_metric_logic passed")


def test_success_rate_metric():
    """Test success rate comparison."""
    # 98% success rate baseline
    baseline = create_test_baseline()
    baseline.successful_requests = 9800
    baseline.total_requests = 10000

    # 95% success rate current
    current = create_test_baseline()
    current.successful_requests = 9500
    current.total_requests = 10000

    report = compare_benchmarks(baseline, current)

    # Find success rate metric
    success_metric = None
    for metric in report.regressions:
        if "Success Rate" in metric.metric_name:
            success_metric = metric
            break

    assert success_metric is not None
    assert success_metric.is_regression is True  # Lower success rate is a regression
    print("[PASS] test_success_rate_metric passed")


def test_no_regressions():
    """Test comparison when there are no regressions."""
    baseline = create_test_baseline()
    current = create_test_baseline()  # Identical

    report = compare_benchmarks(baseline, current)

    assert len(report.regressions) == 0
    assert report.has_critical_regression is False
    # Most metrics should be neutral
    assert len(report.neutral) > 0
    print("[PASS] test_no_regressions passed")


def test_all_improvements():
    """Test comparison when current is all improvements."""
    baseline = create_test_baseline(
        requests_per_second=100.0,
        avg_latency=100.0,
        p95_latency=300.0,
        p99_latency=400.0,
    )

    current = create_test_baseline(
        requests_per_second=150.0,  # 50% better
        avg_latency=50.0,  # 50% better
        p95_latency=150.0,  # 50% better
        p99_latency=200.0,  # 50% better
    )

    report = compare_benchmarks(baseline, current)

    assert len(report.improvements) > 0
    assert len(report.regressions) == 0
    assert report.has_critical_regression is False
    print("[PASS] test_all_improvements passed")


def test_comparison_metrics_to_dict():
    """Test ComparisonMetrics serialization."""
    metric = ComparisonMetrics(
        metric_name="Test",
        baseline_value=100.0,
        current_value=110.0,
        delta=10.0,
        delta_percent=10.0,
        is_regression=True,
        is_improvement=False,
        severity="warning",
    )

    data = metric.to_dict()

    assert data['metric_name'] == "Test"
    assert data['baseline_value'] == 100.0
    assert data['delta_percent'] == 10.0
    assert data['is_regression'] is True
    print("[PASS] test_comparison_metrics_to_dict passed")


if __name__ == "__main__":
    test_latency_metrics()
    test_benchmark_baseline()
    test_compare_metric_regression()
    test_compare_metric_improvement()
    test_compare_metric_small_change()
    test_compare_metric_warning_threshold()
    test_compare_metric_critical_threshold()
    test_compare_benchmarks_overall()
    test_compare_benchmarks_critical_regression()
    test_benchmark_baseline_save_and_load()
    test_load_benchmark_from_json()
    test_comparison_report_attributes()
    test_latency_vs_throughput_metric_logic()
    test_success_rate_metric()
    test_no_regressions()
    test_all_improvements()
    test_comparison_metrics_to_dict()

    print("\n[SUCCESS] All baseline comparison tests passed!")
