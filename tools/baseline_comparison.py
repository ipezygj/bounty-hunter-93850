#!/usr/bin/env python3
"""
Benchmark baseline comparison tool for the Tent of Trials platform.
Provides functionality to save benchmark baselines and compare current results
against historical baselines to detect performance regressions.

Features:
  - Store benchmark results as baselines for future comparison
  - Compare current benchmarks against stored baselines
  - Detect performance regressions and improvements
  - Generate comparison reports with percent deltas
  - Support for multiple baseline versions and rollback
  - Thresholds for warning and failure detection

Usage:
    python3 baseline_comparison.py save <baseline_name> <results_file>
    python3 baseline_comparison.py compare <baseline_name> <results_file>
    python3 baseline_comparison.py list
    python3 baseline_comparison.py show <baseline_name>
    python3 baseline_comparison.py delete <baseline_name>
    python3 baseline_comparison.py report <baseline_name> <results_file>
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import statistics


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

BASELINES_DIR = Path.home() / ".tent_of_trials" / "benchmarks" / "baselines"
BASELINES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------

@dataclass
class LatencyMetrics:
    """Latency metrics from a benchmark result."""
    min_ms: float
    avg_ms: float
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    stddev_ms: float

    @classmethod
    def from_dict(cls, data: Dict) -> 'LatencyMetrics':
        return cls(
            min_ms=data.get('min_ms', data.get('min', 0)),
            avg_ms=data.get('avg_ms', data.get('avg', 0)),
            p50_ms=data.get('p50_ms', data.get('p50', 0)),
            p90_ms=data.get('p90_ms', data.get('p90', 0)),
            p95_ms=data.get('p95_ms', data.get('p95', 0)),
            p99_ms=data.get('p99_ms', data.get('p99', 0)),
            max_ms=data.get('max_ms', data.get('max', 0)),
            stddev_ms=data.get('stddev_ms', data.get('stddev', 0)),
        )

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BenchmarkBaseline:
    """Represents a stored benchmark baseline."""
    name: str
    benchmark_type: str
    timestamp: float
    duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    timeout_requests: int
    requests_per_second: float
    latency_ms: LatencyMetrics
    error_distribution: Dict[str, int]
    target_endpoint: str
    concurrency: int

    @classmethod
    def from_json_file(cls, filepath: Path) -> 'BenchmarkBaseline':
        """Load baseline from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        data['latency_ms'] = LatencyMetrics.from_dict(data.get('latency_ms', {}))
        return cls(**data)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # latency_ms is already a dict from asdict, so no need to convert
        if isinstance(data['latency_ms'], dict):
            pass  # Already converted by asdict
        else:
            data['latency_ms'] = data['latency_ms'].to_dict()
        return data

    def save(self, baseline_name: str) -> Path:
        """Save baseline to file."""
        baseline_path = BASELINES_DIR / f"{baseline_name}.json"
        with open(baseline_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        return baseline_path


@dataclass
class ComparisonMetrics:
    """Metrics comparing current result to baseline."""
    metric_name: str
    baseline_value: float
    current_value: float
    delta: float
    delta_percent: float
    is_regression: bool
    is_improvement: bool
    severity: str  # 'info', 'warning', 'critical'

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ComparisonReport:
    """Report comparing current benchmark to baseline."""
    baseline_name: str
    baseline_timestamp: float
    current_timestamp: float
    benchmark_type: str
    comparison_date: str
    total_comparisons: int
    regressions: List[ComparisonMetrics] = field(default_factory=list)
    improvements: List[ComparisonMetrics] = field(default_factory=list)
    neutral: List[ComparisonMetrics] = field(default_factory=list)
    has_critical_regression: bool = False
    regression_count: int = field(default=0)
    improvement_count: int = field(default=0)

    def __post_init__(self):
        """Update counts based on list contents."""
        self.regression_count = len(self.regressions)
        self.improvement_count = len(self.improvements)

    def to_dict(self) -> Dict:
        return {
            'baseline_name': self.baseline_name,
            'baseline_timestamp': self.baseline_timestamp,
            'current_timestamp': self.current_timestamp,
            'benchmark_type': self.benchmark_type,
            'comparison_date': self.comparison_date,
            'total_comparisons': self.total_comparisons,
            'regressions': [r.to_dict() for r in self.regressions],
            'improvements': [i.to_dict() for i in self.improvements],
            'neutral': [n.to_dict() for n in self.neutral],
            'has_critical_regression': self.has_critical_regression,
            'regression_count': self.regression_count,
            'improvement_count': self.improvement_count,
        }


# ---------------------------------------------------------------------------
# COMPARISON LOGIC
# ---------------------------------------------------------------------------

def load_benchmark_from_json(filepath: Path) -> BenchmarkBaseline:
    """Load a benchmark result from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)

    latency_ms = LatencyMetrics.from_dict(data.get('latency_ms', {}))

    return BenchmarkBaseline(
        name=data.get('benchmark_type', 'unknown'),
        benchmark_type=data.get('benchmark_type', 'unknown'),
        timestamp=data.get('start_time', time.time()),
        duration_seconds=data.get('duration_seconds', 0),
        total_requests=data.get('total_requests', 0),
        successful_requests=data.get('successful_requests', 0),
        failed_requests=data.get('failed_requests', 0),
        timeout_requests=data.get('timeout_requests', 0),
        requests_per_second=data.get('requests_per_second', 0),
        latency_ms=latency_ms,
        error_distribution=data.get('error_distribution', {}),
        target_endpoint=data.get('target_endpoint', ''),
        concurrency=data.get('concurrency', 0),
    )


def compare_metric(metric_name: str, baseline_value: float, current_value: float,
                  warning_threshold: float = 10.0,
                  critical_threshold: float = 25.0) -> ComparisonMetrics:
    """Compare a single metric against baseline.

    Args:
        metric_name: Name of the metric
        baseline_value: Baseline value
        current_value: Current value
        warning_threshold: Percent change threshold for warning
        critical_threshold: Percent change threshold for critical

    Returns:
        ComparisonMetrics with comparison results
    """
    if baseline_value == 0:
        delta = current_value
        delta_percent = 0 if current_value == 0 else float('inf')
    else:
        delta = current_value - baseline_value
        delta_percent = (delta / baseline_value) * 100

    is_regression = delta > 0
    is_improvement = delta < 0

    # Determine severity for regressions (higher latency or lower throughput is bad)
    severity = 'info'
    if is_regression:
        abs_percent = abs(delta_percent)
        if abs_percent >= critical_threshold:
            severity = 'critical'
        elif abs_percent >= warning_threshold:
            severity = 'warning'

    return ComparisonMetrics(
        metric_name=metric_name,
        baseline_value=baseline_value,
        current_value=current_value,
        delta=delta,
        delta_percent=delta_percent,
        is_regression=is_regression,
        is_improvement=is_improvement,
        severity=severity,
    )


def compare_benchmarks(baseline: BenchmarkBaseline, current: BenchmarkBaseline,
                      warning_threshold: float = 10.0,
                      critical_threshold: float = 25.0) -> ComparisonReport:
    """Compare current benchmark against baseline.

    Returns ComparisonReport with all comparisons.
    """
    report = ComparisonReport(
        baseline_name=baseline.name,
        baseline_timestamp=baseline.timestamp,
        current_timestamp=current.timestamp,
        benchmark_type=baseline.benchmark_type,
        comparison_date=datetime.now().isoformat(),
        total_comparisons=0,  # Will be set later
    )

    # Metrics to compare
    metrics_to_compare = [
        ('Requests/sec', baseline.requests_per_second, current.requests_per_second, False),  # False = higher is better
        ('Avg Latency (ms)', baseline.latency_ms.avg_ms, current.latency_ms.avg_ms, True),  # True = lower is better
        ('P50 Latency (ms)', baseline.latency_ms.p50_ms, current.latency_ms.p50_ms, True),
        ('P95 Latency (ms)', baseline.latency_ms.p95_ms, current.latency_ms.p95_ms, True),
        ('P99 Latency (ms)', baseline.latency_ms.p99_ms, current.latency_ms.p99_ms, True),
        ('Max Latency (ms)', baseline.latency_ms.max_ms, current.latency_ms.max_ms, True),
        ('Success Rate (%)', (baseline.successful_requests / max(baseline.total_requests, 1)) * 100,
         (current.successful_requests / max(current.total_requests, 1)) * 100, False),
    ]

    all_comparisons: List[ComparisonMetrics] = []

    for metric_name, baseline_val, current_val, invert_logic in metrics_to_compare:
        # For metrics where lower is better (latency), a positive delta is a regression
        # For metrics where higher is better (throughput), a positive delta is an improvement
        if invert_logic:
            # Latency metrics: lower is better
            comparison = compare_metric(metric_name, baseline_val, current_val,
                                       warning_threshold, critical_threshold)
        else:
            # Throughput metrics: higher is better
            # Invert the logic by comparing in reverse
            comparison = compare_metric(metric_name, baseline_val, current_val,
                                       warning_threshold, critical_threshold)
            # For throughput, positive delta is good, so flip the regression flag
            if metric_name == 'Requests/sec':
                comparison.is_regression = comparison.delta < 0
                comparison.is_improvement = comparison.delta > 0
            elif 'Success Rate' in metric_name:
                comparison.is_regression = comparison.delta < 0
                comparison.is_improvement = comparison.delta > 0

        all_comparisons.append(comparison)

    # Categorize comparisons
    for comparison in all_comparisons:
        if comparison.is_regression:
            report.regressions.append(comparison)
            if comparison.severity == 'critical':
                report.has_critical_regression = True
            report.regression_count += 1
        elif comparison.is_improvement:
            report.improvements.append(comparison)
            report.improvement_count += 1
        else:
            report.neutral.append(comparison)

    report.total_comparisons = len(all_comparisons)

    return report


# ---------------------------------------------------------------------------
# FILE OPERATIONS
# ---------------------------------------------------------------------------

def save_baseline(baseline_name: str, results_file: Path) -> str:
    """Save benchmark results as a baseline.

    Args:
        baseline_name: Name to save baseline as
        results_file: Path to benchmark results JSON file

    Returns:
        Success message
    """
    if not results_file.exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    benchmark = load_benchmark_from_json(results_file)
    benchmark.name = baseline_name
    baseline_path = benchmark.save(baseline_name)

    return f"Baseline '{baseline_name}' saved to {baseline_path}"


def load_baseline(baseline_name: str) -> BenchmarkBaseline:
    """Load a stored baseline.

    Args:
        baseline_name: Name of baseline to load

    Returns:
        BenchmarkBaseline object
    """
    baseline_path = BASELINES_DIR / f"{baseline_name}.json"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline not found: {baseline_name}")

    return BenchmarkBaseline.from_json_file(baseline_path)


def list_baselines() -> List[str]:
    """List all available baselines.

    Returns:
        List of baseline names
    """
    baselines = []
    for filepath in BASELINES_DIR.glob("*.json"):
        baselines.append(filepath.stem)
    return sorted(baselines)


def delete_baseline(baseline_name: str) -> str:
    """Delete a baseline.

    Args:
        baseline_name: Name of baseline to delete

    Returns:
        Success message
    """
    baseline_path = BASELINES_DIR / f"{baseline_name}.json"
    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline not found: {baseline_name}")

    baseline_path.unlink()
    return f"Baseline '{baseline_name}' deleted"


def show_baseline(baseline_name: str) -> str:
    """Show baseline details.

    Args:
        baseline_name: Name of baseline to show

    Returns:
        Formatted baseline information
    """
    baseline = load_baseline(baseline_name)
    data = baseline.to_dict()
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# REPORTING
# ---------------------------------------------------------------------------

def print_comparison_report(report: ComparisonReport):
    """Print comparison report in human-readable format."""
    print(f"\n{'='*70}")
    print(f"  BENCHMARK COMPARISON REPORT")
    print(f"  Baseline: {report.baseline_name}")
    print(f"  Type: {report.benchmark_type.upper()}")
    print(f"{'='*70}")

    baseline_date = datetime.fromtimestamp(report.baseline_timestamp).isoformat()
    current_date = datetime.fromtimestamp(report.current_timestamp).isoformat()
    print(f"  Baseline Date: {baseline_date}")
    print(f"  Current Date:  {current_date}")
    print(f"  Report Date:   {report.comparison_date}")

    print(f"\n{'-'*70}")
    print(f"  SUMMARY")
    print(f"  Total Metrics Compared: {report.total_comparisons}")
    print(f"  Regressions:            {report.regression_count}")
    print(f"  Improvements:           {report.improvement_count}")
    print(f"  Neutral:                {len(report.neutral)}")

    if report.has_critical_regression:
        print(f"  [ALERT] CRITICAL REGRESSION DETECTED!")

    print(f"{'-'*70}")

    if report.regressions:
        print(f"\n  REGRESSIONS (Performance Degradation):")
        for metric in sorted(report.regressions, key=lambda m: m.delta_percent, reverse=True):
            symbol = "[CRIT]" if metric.severity == 'critical' else "[WARN]" if metric.severity == 'warning' else "[INFO]"
            print(f"    {symbol} {metric.metric_name}")
            print(f"       Baseline: {metric.baseline_value:.2f}")
            print(f"       Current:  {metric.current_value:.2f}")
            print(f"       Delta:    {metric.delta:+.2f} ({metric.delta_percent:+.2f}%)")
            print()

    if report.improvements:
        print(f"\n  IMPROVEMENTS (Performance Enhancement):")
        for metric in sorted(report.improvements, key=lambda m: m.delta_percent):
            print(f"    [GOOD] {metric.metric_name}")
            print(f"       Baseline: {metric.baseline_value:.2f}")
            print(f"       Current:  {metric.current_value:.2f}")
            print(f"       Delta:    {metric.delta:+.2f} ({metric.delta_percent:+.2f}%)")
            print()

    if report.neutral:
        print(f"\n  NO SIGNIFICANT CHANGE:")
        for metric in report.neutral:
            print(f"    [NEUT] {metric.metric_name}")
            print(f"       Baseline: {metric.baseline_value:.2f}")
            print(f"       Current:  {metric.current_value:.2f}")
            print(f"       Delta:    {metric.delta:+.2f} ({metric.delta_percent:+.2f}%)")
            print()

    print(f"{'='*70}\n", end='', flush=True)

    return 0 if not report.has_critical_regression else 1


def generate_comparison_report(baseline_name: str, results_file: Path) -> Tuple[ComparisonReport, int]:
    """Generate and return comparison report.

    Args:
        baseline_name: Name of baseline to compare against
        results_file: Path to current benchmark results

    Returns:
        Tuple of (ComparisonReport, exit_code)
    """
    if not results_file.exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")

    baseline = load_baseline(baseline_name)
    current = load_benchmark_from_json(results_file)

    report = compare_benchmarks(baseline, current)
    exit_code = print_comparison_report(report)

    return report, exit_code


import time


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark baseline comparison tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Save current results as a baseline:
    python3 baseline_comparison.py save production results.json

  Compare against a baseline:
    python3 baseline_comparison.py compare production results.json

  List all baselines:
    python3 baseline_comparison.py list

  Show baseline details:
    python3 baseline_comparison.py show production

  Generate comparison report and save to JSON:
    python3 baseline_comparison.py report production results.json --output report.json

  Delete a baseline:
    python3 baseline_comparison.py delete production
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Save command
    save_p = subparsers.add_parser("save", help="Save benchmark results as baseline")
    save_p.add_argument("name", help="Baseline name")
    save_p.add_argument("file", type=Path, help="Benchmark results JSON file")

    # Compare command
    compare_p = subparsers.add_parser("compare", help="Compare against baseline")
    compare_p.add_argument("name", help="Baseline name")
    compare_p.add_argument("file", type=Path, help="Benchmark results JSON file")
    compare_p.add_argument("--output", "-o", type=Path, help="Save comparison report to JSON")

    # List command
    subparsers.add_parser("list", help="List all baselines")

    # Show command
    show_p = subparsers.add_parser("show", help="Show baseline details")
    show_p.add_argument("name", help="Baseline name")

    # Delete command
    delete_p = subparsers.add_parser("delete", help="Delete a baseline")
    delete_p.add_argument("name", help="Baseline name")

    # Report command
    report_p = subparsers.add_parser("report", help="Generate comparison report")
    report_p.add_argument("name", help="Baseline name")
    report_p.add_argument("file", type=Path, help="Benchmark results JSON file")
    report_p.add_argument("--output", "-o", type=Path, help="Save report to JSON")

    args = parser.parse_args()

    try:
        if args.command == "save":
            message = save_baseline(args.name, args.file)
            print(message)
            return 0

        elif args.command == "compare":
            report, exit_code = generate_comparison_report(args.name, args.file)
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(report.to_dict(), f, indent=2)
                print(f"Report saved to {args.output}")
            return exit_code

        elif args.command == "list":
            baselines = list_baselines()
            if baselines:
                print(f"Available baselines ({len(baselines)}):")
                for baseline_name in baselines:
                    baseline = load_baseline(baseline_name)
                    date = datetime.fromtimestamp(baseline.timestamp).isoformat()
                    print(f"  - {baseline_name} ({baseline.benchmark_type}, {date})")
            else:
                print("No baselines found")
            return 0

        elif args.command == "show":
            print(show_baseline(args.name))
            return 0

        elif args.command == "delete":
            message = delete_baseline(args.name)
            print(message)
            return 0

        elif args.command == "report":
            report, exit_code = generate_comparison_report(args.name, args.file)
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(report.to_dict(), f, indent=2)
                print(f"Report saved to {args.output}")
            return exit_code

        else:
            parser.print_help()
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
