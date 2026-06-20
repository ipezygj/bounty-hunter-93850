# Benchmark Baseline Comparison Tool

A comprehensive tool for tracking and comparing benchmark results against baseline performance metrics to detect performance regressions and improvements.

## Overview

The baseline comparison tool enables:

- **Baseline Management**: Save benchmark results as baselines for future comparison
- **Performance Tracking**: Compare current benchmarks against historical baselines
- **Regression Detection**: Automatically detect performance regressions with configurable severity levels
- **Detailed Reporting**: Generate comprehensive HTML and JSON comparison reports
- **Metrics Analysis**: Compare latency percentiles, throughput, and success rates

## Features

### Metrics Tracked

The tool compares the following metrics:

- **Requests/sec**: Throughput measurement
- **Avg Latency (ms)**: Average response time
- **P50 Latency (ms)**: Median response time
- **P90 Latency (ms)**: 90th percentile response time
- **P95 Latency (ms)**: 95th percentile response time
- **P99 Latency (ms)**: 99th percentile response time
- **Max Latency (ms)**: Maximum response time
- **Success Rate (%)**: Percentage of successful requests

### Severity Levels

Regressions are categorized by severity:

- **CRITICAL**: >= 25% change from baseline
- **WARNING**: 10-25% change from baseline
- **INFO**: < 10% change from baseline

## Installation

The tool is included in the `tools/` directory. No additional dependencies beyond Python 3.7+ are required.

## Usage

### Command Line Interface

#### Save a Baseline

Save current benchmark results as a named baseline for future comparison:

```bash
python3 baseline_comparison.py save <baseline_name> <results_file>
```

Example:
```bash
python3 baseline_comparison.py save production results.json
python3 baseline_comparison.py save staging v2_latency.json
```

#### Compare Against a Baseline

Compare current benchmark results against a saved baseline:

```bash
python3 baseline_comparison.py compare <baseline_name> <results_file>
```

Example:
```bash
python3 baseline_comparison.py compare production current_results.json
```

This prints a detailed report showing:
- Summary of changes (regressions, improvements, neutral)
- Detailed metrics comparison with delta and percent change
- Severity classification for each regression
- Critical regression alerts

#### List All Baselines

View all saved baselines:

```bash
python3 baseline_comparison.py list
```

Output example:
```
Available baselines (3):
  - production (latency, 2023-12-20T19:00:00)
  - staging (latency, 2023-12-15T14:30:00)
  - v1_baseline (latency, 2023-12-10T10:15:00)
```

#### Show Baseline Details

Display the full details of a specific baseline:

```bash
python3 baseline_comparison.py show <baseline_name>
```

#### Generate Comparison Report

Generate a detailed comparison report and save to JSON file:

```bash
python3 baseline_comparison.py report <baseline_name> <results_file> --output <report_file>
```

Example:
```bash
python3 baseline_comparison.py report production results.json --output comparison_report.json
```

#### Delete a Baseline

Remove a saved baseline:

```bash
python3 baseline_comparison.py delete <baseline_name>
```

## Input Format

Benchmark results should be in JSON format with the following structure:

```json
{
  "benchmark_type": "latency",
  "start_time": 1703088000.0,
  "end_time": 1703088060.0,
  "duration_seconds": 60.0,
  "total_requests": 6000,
  "successful_requests": 5900,
  "failed_requests": 100,
  "timeout_requests": 0,
  "requests_per_second": 100.0,
  "latency_ms": {
    "min": 10.0,
    "avg": 50.0,
    "p50": 40.0,
    "p90": 100.0,
    "p95": 150.0,
    "p99": 200.0,
    "max": 500.0,
    "stddev": 20.0
  },
  "error_distribution": {
    "timeout": 0,
    "5xx": 100
  },
  "target_endpoint": "http://localhost:8080/health",
  "concurrency": 10
}
```

## Output Format

### Console Output

Comparison reports are displayed in a human-readable format:

```
======================================================================
  BENCHMARK COMPARISON REPORT
  Baseline: production
  Type: LATENCY
======================================================================
  Baseline Date: 2023-12-20T19:00:00
  Current Date:  2023-12-20T19:02:00
  Report Date:   2026-06-21T00:50:48.968606

----------------------------------------------------------------------
  SUMMARY
  Total Metrics Compared: 7
  Regressions:            7
  Improvements:           0
  Neutral:                0
  [ALERT] CRITICAL REGRESSION DETECTED!
----------------------------------------------------------------------

  REGRESSIONS (Performance Degradation):
    [CRIT] P50 Latency (ms)
       Baseline: 40.00
       Current:  70.00
       Delta:    +30.00 (+75.00%)

    [WARN] Requests/sec
       Baseline: 100.00
       Current:  95.00
       Delta:    -5.00 (-5.00%)
```

### JSON Output

Detailed JSON reports contain all metrics and comparisons:

```json
{
  "baseline_name": "production",
  "baseline_timestamp": 1703088000.0,
  "current_timestamp": 1703088120.0,
  "benchmark_type": "latency",
  "comparison_date": "2026-06-21T00:50:53.718166",
  "total_comparisons": 7,
  "regressions": [
    {
      "metric_name": "Avg Latency (ms)",
      "baseline_value": 50.0,
      "current_value": 85.0,
      "delta": 35.0,
      "delta_percent": 70.0,
      "is_regression": true,
      "is_improvement": false,
      "severity": "critical"
    }
  ],
  "improvements": [],
  "neutral": [],
  "has_critical_regression": true,
  "regression_count": 7,
  "improvement_count": 0
}
```

## Exit Codes

- `0`: Comparison completed successfully (no critical regressions)
- `1`: Comparison completed with critical regressions detected OR error occurred

## Storage

Baselines are stored in the user's home directory:

```
~/.tent_of_trials/benchmarks/baselines/
```

Each baseline is saved as a JSON file named `<baseline_name>.json`

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Run benchmark
  run: python3 tools/benchmark.py latency --output results.json

- name: Compare against baseline
  run: python3 tools/baseline_comparison.py compare production results.json
  continue-on-error: true

- name: Generate report
  if: always()
  run: python3 tools/baseline_comparison.py report production results.json --output report.json

- name: Upload report
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: benchmark-report
    path: report.json
```

### Fail on Critical Regression

```bash
#!/bin/bash
python3 tools/baseline_comparison.py compare production results.json
if [ $? -eq 1 ]; then
  echo "Critical performance regression detected!"
  exit 1
fi
```

## Testing

Comprehensive test suite is included in `test_baseline_comparison.py`:

```bash
python3 tools/test_baseline_comparison.py
```

Tests cover:
- Metric comparison logic
- Regression and improvement detection
- Severity classification
- Baseline save/load operations
- Report generation
- Data serialization

## Python API

The tool can also be used as a Python library:

```python
from baseline_comparison import (
    load_baseline, load_benchmark_from_json,
    compare_benchmarks, print_comparison_report
)

# Load baseline and current results
baseline = load_baseline("production")
current = load_benchmark_from_json("results.json")

# Compare benchmarks
report = compare_benchmarks(baseline, current)

# Print or process the report
print_comparison_report(report)
```

## Troubleshooting

### Baseline Not Found

Ensure the baseline exists by listing available baselines:

```bash
python3 baseline_comparison.py list
```

### Results File Not Found

Check that the results file path is correct and the file exists:

```bash
ls -la <results_file>
```

### Character Encoding Issues

The tool uses ASCII-safe characters for compatibility with various terminals and CI systems. If you see encoding errors, ensure your terminal is configured to handle UTF-8 output.

## Performance Considerations

- Baselines are stored locally and don't require network access
- Comparison operations are fast (< 100ms for typical benchmarks)
- JSON reports are human-readable and suitable for archiving
- Storage is minimal (< 1KB per baseline)

## Future Enhancements

Potential additions:
- Multiple baseline versions with automatic rollback
- Custom thresholds per metric
- Trend analysis over multiple baselines
- HTML report generation
- Integration with monitoring systems
- Statistical significance testing
- Performance budgets and SLOs

## License

Same as parent Tent of Trials project.
