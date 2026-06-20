#!/usr/bin/env python3
"""
Tests for AI Reviewer Ignore Configuration
===========================================

Tests the ignore config functionality including:
- Config file loading (JSON, YAML)
- Filtering by rule, category, severity
- File pattern matching
- CLI argument parsing
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ai_reviewer import (
    AiCodeReviewer,
    IgnoreConfig,
    IgnoreConfigLoader,
    ReviewCategory,
    ReviewFinding,
    ReviewSeverity,
)


class TestIgnoreConfig(unittest.TestCase):
    """Tests for IgnoreConfig class."""

    def test_empty_config(self):
        """Test empty ignore config doesn't filter anything."""
        config = IgnoreConfig()
        finding = ReviewFinding(
            id="test-1",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.STYLE,
            message="Test message",
            file_path="test.py",
            line_number=1,
            rules=["STYLE-TEST"],
        )
        self.assertFalse(config.should_ignore_finding(finding))

    def test_ignore_by_rule(self):
        """Test filtering by rule ID."""
        config = IgnoreConfig(ignored_rules={"STYLE-TEST", "SEC-SQL"})
        finding = ReviewFinding(
            id="test-1",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.STYLE,
            message="Test message",
            file_path="test.py",
            line_number=1,
            rules=["STYLE-TEST"],
        )
        self.assertTrue(config.should_ignore_finding(finding))

        # Different rule should not be ignored
        finding2 = ReviewFinding(
            id="test-2",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.STYLE,
            message="Test message",
            file_path="test.py",
            line_number=1,
            rules=["STYLE-OTHER"],
        )
        self.assertFalse(config.should_ignore_finding(finding2))

    def test_ignore_by_category(self):
        """Test filtering by category."""
        config = IgnoreConfig(ignored_categories={ReviewCategory.STYLE})
        finding = ReviewFinding(
            id="test-1",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.STYLE,
            message="Test message",
            file_path="test.py",
            line_number=1,
        )
        self.assertTrue(config.should_ignore_finding(finding))

        # Different category should not be ignored
        finding2 = ReviewFinding(
            id="test-2",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.SECURITY,
            message="Test message",
            file_path="test.py",
            line_number=1,
        )
        self.assertFalse(config.should_ignore_finding(finding2))

    def test_ignore_by_severity(self):
        """Test filtering by severity."""
        config = IgnoreConfig(ignored_severities={ReviewSeverity.INFO})
        finding = ReviewFinding(
            id="test-1",
            severity=ReviewSeverity.INFO,
            category=ReviewCategory.STYLE,
            message="Test message",
            file_path="test.py",
            line_number=1,
        )
        self.assertTrue(config.should_ignore_finding(finding))

        # Different severity should not be ignored
        finding2 = ReviewFinding(
            id="test-2",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.STYLE,
            message="Test message",
            file_path="test.py",
            line_number=1,
        )
        self.assertFalse(config.should_ignore_finding(finding2))

    def test_ignore_by_message_substring(self):
        """Test filtering by message substring."""
        config = IgnoreConfig(ignored_messages={"test pattern", "line length"})
        finding = ReviewFinding(
            id="test-1",
            severity=ReviewSeverity.INFO,
            category=ReviewCategory.STYLE,
            message="This is a test pattern violation",
            file_path="test.py",
            line_number=1,
        )
        self.assertTrue(config.should_ignore_finding(finding))

        finding2 = ReviewFinding(
            id="test-2",
            severity=ReviewSeverity.INFO,
            category=ReviewCategory.STYLE,
            message="Line exceeds line length limit",
            file_path="test.py",
            line_number=1,
        )
        self.assertTrue(config.should_ignore_finding(finding2))

        # Different message should not be ignored
        finding3 = ReviewFinding(
            id="test-3",
            severity=ReviewSeverity.INFO,
            category=ReviewCategory.STYLE,
            message="Some other issue",
            file_path="test.py",
            line_number=1,
        )
        self.assertFalse(config.should_ignore_finding(finding3))

    def test_ignore_by_file_pattern(self):
        """Test filtering by file glob patterns."""
        config = IgnoreConfig(ignored_files={"*.test.py", "migrations/*", "**/generated/*"})

        # File matching *.test.py
        self.assertTrue(config.should_ignore_file("test.test.py"))
        self.assertTrue(config.should_ignore_file("/path/to/unit.test.py"))

        # File matching migrations/*
        self.assertTrue(config.should_ignore_file("migrations/001_init.py"))

        # File not matching any pattern
        self.assertFalse(config.should_ignore_file("main.py"))

    def test_multiple_filters(self):
        """Test config with multiple filter types."""
        config = IgnoreConfig(
            ignored_rules={"STYLE-TEST"},
            ignored_categories={ReviewCategory.DOCUMENTATION},
            ignored_severities={ReviewSeverity.SUGGESTION},
        )

        # Should ignore by rule
        finding1 = ReviewFinding(
            id="1",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.STYLE,
            message="msg",
            file_path="test.py",
            line_number=1,
            rules=["STYLE-TEST"],
        )
        self.assertTrue(config.should_ignore_finding(finding1))

        # Should ignore by category
        finding2 = ReviewFinding(
            id="2",
            severity=ReviewSeverity.WARNING,
            category=ReviewCategory.DOCUMENTATION,
            message="msg",
            file_path="test.py",
            line_number=1,
        )
        self.assertTrue(config.should_ignore_finding(finding2))

        # Should ignore by severity
        finding3 = ReviewFinding(
            id="3",
            severity=ReviewSeverity.SUGGESTION,
            category=ReviewCategory.STYLE,
            message="msg",
            file_path="test.py",
            line_number=1,
        )
        self.assertTrue(config.should_ignore_finding(finding3))


class TestIgnoreConfigLoader(unittest.TestCase):
    """Tests for IgnoreConfigLoader class."""

    def test_load_json_config(self):
        """Test loading JSON configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "ai-reviewer-ignore.json"
            config_file.write_text(
                json.dumps(
                    {
                        "rules": ["STYLE-TEST", "PERF-NPLUS1"],
                        "categories": ["documentation"],
                        "severities": ["suggestion"],
                    }
                )
            )

            config = IgnoreConfigLoader.load_config(config_path=config_file)
            self.assertEqual(config.ignored_rules, {"STYLE-TEST", "PERF-NPLUS1"})
            self.assertIn(ReviewCategory.DOCUMENTATION, config.ignored_categories)
            self.assertIn(ReviewSeverity.SUGGESTION, config.ignored_severities)

    def test_load_json_config_with_lists_and_strings(self):
        """Test loading JSON with mixed list and string formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text(
                json.dumps(
                    {
                        "rules": "SINGLE-RULE",
                        "files": ["*.test.py", "migrations/*"],
                        "messages": "debug output",
                    }
                )
            )

            config = IgnoreConfigLoader.load_config(config_path=config_file)
            self.assertEqual(config.ignored_rules, {"SINGLE-RULE"})
            self.assertEqual(config.ignored_files, {"*.test.py", "migrations/*"})
            self.assertEqual(config.ignored_messages, {"debug output"})

    def test_load_yaml_config(self):
        """Test loading YAML configuration (if PyYAML installed)."""
        try:
            import yaml

            with tempfile.TemporaryDirectory() as tmpdir:
                config_file = Path(tmpdir) / "ai-reviewer-ignore.yaml"
                config_file.write_text(
                    """
rules:
  - STYLE-TEST
  - PERF-NPLUS1
categories:
  - style
severities:
  - info
files:
  - "*.test.py"
"""
                )

                config = IgnoreConfigLoader.load_config(config_path=config_file)
                self.assertEqual(config.ignored_rules, {"STYLE-TEST", "PERF-NPLUS1"})
                self.assertIn(ReviewCategory.STYLE, config.ignored_categories)
                self.assertIn(ReviewSeverity.INFO, config.ignored_severities)
                self.assertEqual(config.ignored_files, {"*.test.py"})
        except ImportError:
            self.skipTest("PyYAML not installed")

    def test_load_nonexistent_file(self):
        """Test loading nonexistent file returns empty config."""
        config = IgnoreConfigLoader.load_config(config_path=Path("/nonexistent/path.json"))
        self.assertEqual(len(config.ignored_rules), 0)
        self.assertEqual(len(config.ignored_categories), 0)

    def test_load_invalid_json(self):
        """Test loading invalid JSON returns empty config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text("{ invalid json }")

            config = IgnoreConfigLoader.load_config(config_path=config_file)
            self.assertEqual(len(config.ignored_rules), 0)

    def test_find_default_config(self):
        """Test finding default config files in project root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create a default config file
            config_file = project_root / ".ai-reviewer-ignore.json"
            config_file.write_text(
                json.dumps(
                    {
                        "rules": ["TEST-RULE"],
                    }
                )
            )

            config = IgnoreConfigLoader.load_config(project_root=project_root)
            self.assertEqual(config.ignored_rules, {"TEST-RULE"})


class TestAiCodeReviewerWithIgnore(unittest.TestCase):
    """Tests for AiCodeReviewer with ignore config."""

    def test_reviewer_init_with_ignore_config(self):
        """Test AiCodeReviewer initialization with ignore config."""
        config = IgnoreConfig(ignored_rules={"STYLE-TEST"})
        reviewer = AiCodeReviewer(ignore_config=config)
        self.assertIsNotNone(reviewer.ignore_config)
        self.assertEqual(reviewer.ignore_config.ignored_rules, {"STYLE-TEST"})

    def test_reviewer_init_with_config_path(self):
        """Test AiCodeReviewer initialization with config file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text(json.dumps({"rules": ["TEST-RULE"]}))

            reviewer = AiCodeReviewer(config_path=config_file)
            self.assertEqual(reviewer.ignore_config.ignored_rules, {"TEST-RULE"})

    def test_reviewer_filters_findings(self):
        """Test that reviewer filters findings based on ignore config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python file with long lines
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text(
                "# This is a very long line that exceeds the default limit and should be ignored based on the configuration\nx = 1\n"
            )

            # Create ignore config to skip style issues
            config = IgnoreConfig(ignored_categories={ReviewCategory.STYLE})
            reviewer = AiCodeReviewer(ignore_config=config)

            result = reviewer.review_file(test_file)
            # Should have no style findings due to ignore config
            style_findings = [f for f in result.findings if f.category == ReviewCategory.STYLE]
            self.assertEqual(len(style_findings), 0)

    def test_reviewer_skips_ignored_files(self):
        """Test that reviewer skips files matching ignore patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.generated.py"
            test_file.write_text("x = 1\n")

            config = IgnoreConfig(ignored_files={"*.generated.py"})
            reviewer = AiCodeReviewer(ignore_config=config)

            result = reviewer.review_file(test_file)
            self.assertEqual(result.line_count, 0)
            self.assertIn("Skipped", result.summary)


class TestCLIIntegration(unittest.TestCase):
    """Tests for CLI with ignore config arguments."""

    def test_parser_ignore_config_arg(self):
        """Test parser accepts ignore-config argument."""
        from ai_reviewer import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--path",
                "/test",
                "--ignore-config",
                "/path/to/config.json",
            ]
        )
        self.assertEqual(args.ignore_config, "/path/to/config.json")

    def test_parser_ignore_rule_args(self):
        """Test parser accepts ignore-rule arguments."""
        from ai_reviewer import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--path",
                "/test",
                "--ignore-rule",
                "STYLE-TEST",
                "--ignore-rule",
                "PERF-NPLUS1",
            ]
        )
        self.assertEqual(args.ignore_rules, ["STYLE-TEST", "PERF-NPLUS1"])

    def test_parser_ignore_category_args(self):
        """Test parser accepts ignore-category arguments."""
        from ai_reviewer import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--path",
                "/test",
                "--ignore-category",
                "style",
                "--ignore-category",
                "documentation",
            ]
        )
        self.assertEqual(args.ignore_categories, ["style", "documentation"])

    def test_parser_ignore_severity_args(self):
        """Test parser accepts ignore-severity arguments."""
        from ai_reviewer import create_parser

        parser = create_parser()
        args = parser.parse_args(
            [
                "--path",
                "/test",
                "--ignore-severity",
                "info",
                "--ignore-severity",
                "suggestion",
            ]
        )
        self.assertEqual(args.ignore_severities, ["info", "suggestion"])


if __name__ == "__main__":
    unittest.main()
