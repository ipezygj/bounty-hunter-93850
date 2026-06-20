# AI Reviewer Ignore Configuration

The AI Code Reviewer now supports ignore configuration to skip specific code review checks. This allows teams to customize the review process and exclude certain rules, categories, file patterns, or severity levels.

## Features

- **Ignore specific rules** by their ID (e.g., `STYLE-LINE-LENGTH`, `SEC-SQL-INJECTION`)
- **Ignore review categories** (e.g., `style`, `security`, `performance`, `documentation`)
- **Ignore severity levels** (e.g., `info`, `suggestion`, `warning`, `error`, `critical`)
- **Ignore entire files** using glob patterns (e.g., `*.test.py`, `migrations/*`)
- **Ignore by message patterns** (substring matching)
- **Multiple configuration formats**: JSON and YAML
- **Automatic config discovery**: Searches for default config files in project root
- **CLI argument support**: Override config with command-line arguments

## Configuration Files

The reviewer automatically searches for configuration files in this order:

1. `.ai-reviewer-ignore`
2. `.ai-reviewer-ignore.json`
3. `.ai-reviewer-ignore.yaml`
4. `.ai-reviewer-ignore.yml`
5. `ai-reviewer-ignore.json`
6. `ai-reviewer-ignore.yaml`

### JSON Format

```json
{
  "rules": ["STYLE-LINE-LENGTH", "PERF-NPLUS1"],
  "categories": ["documentation", "testing"],
  "severities": ["suggestion", "info"],
  "files": ["*.generated.py", "migrations/*.py"],
  "messages": ["debug output", "test pattern"]
}
```

### YAML Format

```yaml
rules:
  - STYLE-LINE-LENGTH
  - PERF-NPLUS1

categories:
  - documentation
  - testing

severities:
  - suggestion
  - info

files:
  - "*.generated.py"
  - "migrations/*.py"

messages:
  - "debug output"
  - "test pattern"
```

## Available Rules

Security rules:
- `SEC-SQL-INJECTION`
- `SEC-XSS`
- `SEC-COMMAND-INJECTION`
- `SEC-HARDCODED-KEY`
- `SEC-PATH-TRAVERSAL`
- `SEC-INSECURE-RANDOM`
- `SEC-INSECURE-COOKIE`
- `SEC-XXE`

Style rules:
- `STYLE-LINE-LENGTH`

Complexity rules:
- `CMPLX-CYCLOMATIC`
- `CMPLX-COGNITIVE`
- `CMPLX-PARAMETER-COUNT`

Performance rules:
- `PERF-NPLUS1`
- `PERF-LARGE-ARRAY`
- `PERF-RECURSION`

Pattern-based rules:
- `PATTERN-*` (depends on ai_migrator patterns)

## Categories

- `style`: Code style and formatting issues
- `complexity`: Cyclomatic/cognitive complexity warnings
- `security`: Security vulnerabilities
- `performance`: Performance anti-patterns
- `maintainability`: Code maintainability issues
- `best-practice`: Best practice violations
- `documentation`: Documentation-related issues
- `testing`: Testing-related issues
- `dependency`: Dependency-related issues
- `duplication`: Code duplication

## Severity Levels

- `critical`: Critical issues that should be fixed immediately
- `error`: Error-level issues
- `warning`: Warning-level issues
- `info`: Information-level findings
- `suggestion`: Suggestions for improvement

## Usage

### Using Configuration File

1. Create `.ai-reviewer-ignore.json` in your project root:

```json
{
  "categories": ["documentation"],
  "severities": ["suggestion"],
  "files": ["*.test.py"]
}
```

2. Run the reviewer (it will auto-load the config):

```bash
python ai_reviewer.py --path ./src
```

### Using Command-Line Arguments

Ignore specific rules:
```bash
python ai_reviewer.py --path ./src --ignore-rule STYLE-LINE-LENGTH --ignore-rule PERF-NPLUS1
```

Ignore categories:
```bash
python ai_reviewer.py --path ./src --ignore-category style --ignore-category documentation
```

Ignore severity levels:
```bash
python ai_reviewer.py --path ./src --ignore-severity info --ignore-severity suggestion
```

Specify config file explicitly:
```bash
python ai_reviewer.py --path ./src --ignore-config ./custom-ignore-config.json
```

### Combining Config File and CLI Arguments

If both are provided, CLI arguments override the config file:

```bash
python ai_reviewer.py --path ./src --ignore-config custom.json --ignore-rule STYLE-LINE-LENGTH
```

## Examples

### Example 1: Ignore All Style and Documentation Issues

```json
{
  "categories": ["style", "documentation"]
}
```

### Example 2: Ignore Low-Severity Findings

```json
{
  "severities": ["info", "suggestion"]
}
```

### Example 3: Ignore Generated and Test Files

```json
{
  "files": [
    "*.generated.py",
    "*_pb2.py",
    "tests/**/*.py",
    "**/test_*.py"
  ]
}
```

### Example 4: Strict Security Only

Ignore everything except security issues:

```json
{
  "categories": [
    "style",
    "documentation",
    "testing",
    "performance",
    "maintainability"
  ]
}
```

### Example 5: Complex Configuration

```yaml
# Ignore specific security checks that are false positives in your codebase
rules:
  - SEC-HARDCODED-KEY  # Using config file instead

# Ignore documentation warnings for generated code
categories:
  - documentation
  - testing

# Ignore low-severity findings during development
severities:
  - suggestion
  - info

# Ignore auto-generated and vendor code
files:
  - "*.pb2.py"           # Protobuf generated files
  - "*_generated.py"      # Any generated files
  - "migrations/*.py"     # Database migrations
  - "vendor/**"           # Third-party code
  - "build/**"            # Build artifacts

# Ignore findings matching these patterns
messages:
  - "TODO:"
  - "experimental"
  - "debug"
```

## Implementation Details

### IgnoreConfig Class

The `IgnoreConfig` dataclass stores ignored rules, categories, severities, files, and message patterns:

```python
@dataclass
class IgnoreConfig:
    ignored_rules: Set[str] = field(default_factory=set)
    ignored_categories: Set[ReviewCategory] = field(default_factory=set)
    ignored_severities: Set[ReviewSeverity] = field(default_factory=set)
    ignored_files: Set[str] = field(default_factory=set)
    ignored_messages: Set[str] = field(default_factory=set)

    def should_ignore_finding(self, finding: ReviewFinding) -> bool:
        """Check if a finding should be ignored."""

    def should_ignore_file(self, file_path: str) -> bool:
        """Check if a file should be ignored."""
```

### IgnoreConfigLoader Class

Loads configuration from JSON or YAML files and searches for default config files.

### Integration with AiCodeReviewer

The `AiCodeReviewer` class now:
- Accepts optional `ignore_config` parameter
- Accepts optional `config_path` parameter
- Auto-loads config from project root if neither is provided
- Filters findings before adding to results
- Skips entire files if they match ignore patterns

## Testing

Run the comprehensive test suite:

```bash
python -m pytest test_ai_reviewer_ignore.py -v
```

Tests cover:
- Filtering by rule ID
- Filtering by category
- Filtering by severity
- Filtering by file pattern
- Filtering by message substring
- JSON and YAML config loading
- Default config file discovery
- CLI argument parsing
- Integration with AiCodeReviewer

## Backward Compatibility

The ignore configuration feature is completely backward compatible. Existing code that doesn't use ignore config will work exactly as before. The reviewer will simply return all findings without filtering.

## Performance

File pattern matching uses Python's `fnmatch` module with optimized glob patterns. Config loading is performed once at reviewer initialization, not per file, ensuring minimal performance impact.

## Future Enhancements

Potential improvements:
- Regex pattern matching for message filtering
- Per-file configuration overrides
- Time-based ignore rules (e.g., ignore until date)
- Ignore statistics and reporting
- Integration with `# pragma: ignore` comments in code
