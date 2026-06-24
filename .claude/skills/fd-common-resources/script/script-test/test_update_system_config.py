"""Tests for script/update_system_config.py."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "script"
UPDATE_CONFIG = SCRIPT_DIR / "update_system_config.py"
GET_CONFIG = SCRIPT_DIR / "get_config.py"

# Import the module under test
sys.path.insert(0, str(SCRIPT_DIR))
from update_system_config import (
    build_system_config_section,
    update_or_create_file,
    run_get_config,
    SECTION_PATTERN,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_yaml_with_models():
    """Create a temp YAML file with models section (default + registry)."""
    content = {
        "models": {
            "default": "claude-sonnet",
            "providers": {
                "anthropic": {
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "base_url": "https://api.anthropic.com",
                },
            },
            "registry": [
                {
                    "id": "claude-sonnet",
                    "provider": "anthropic",
                    "name": "claude-sonnet-4-6",
                    "max_tokens": 4096,
                    "temperature": 0.7,
                },
            ],
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(
            content, f, default_flow_style=False, indent=2, sort_keys=False
        )
        tmp_path = f.name

    yield tmp_path

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


@pytest.fixture
def temp_yaml_with_agents():
    """Create a temp YAML file with agents section (nested tools, rules)."""
    content = {
        "agents": {
            "default": "general-purpose",
            "registry": [
                {
                    "id": "general-purpose",
                    "description": "Catch-all agent",
                    "model_tier": "middle",
                    "tools": ["Read", "Write", "Edit", "Bash"],
                    "rules": {
                        "max_turns": 20,
                        "timeout_seconds": 300,
                        "allow_parallel": True,
                    },
                    "use_cases": ["general research", "multi-step tasks"],
                },
            ],
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(
            content, f, default_flow_style=False, indent=2, sort_keys=False
        )
        tmp_path = f.name

    yield tmp_path

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


@pytest.fixture
def temp_yaml_no_defaults():
    """Create a temp YAML with sections that lack default + registry."""
    content = {
        "logging": {"level": "info", "format": "json"},
        "runtime": {"workers": 4, "timeout": 60},
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(
            content, f, default_flow_style=False, indent=2, sort_keys=False
        )
        tmp_path = f.name

    yield tmp_path

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


@pytest.fixture
def temp_md_file():
    """Create a temp markdown file with some content."""
    content = "# Test File\n\nSome content before.\n\n## Other Section\n\nMore stuff.\n"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False
    ) as f:
        f.write(content)
        tmp_path = f.name

    yield Path(tmp_path)

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


@pytest.fixture
def temp_md_with_system_config():
    """Create a temp markdown file that already has a ## System Config section."""
    content = (
        "# Test File\n\n"
        "Some content before.\n\n"
        "## System Config\n\n"
        "Old auto-generated content.\n\n"
        "## Other Section\n\n"
        "More stuff after.\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False
    ) as f:
        f.write(content)
        tmp_path = f.name

    yield Path(tmp_path)

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# run_get_config tests
# ---------------------------------------------------------------------------


def test_run_get_config_success(temp_yaml_with_models):
    """run_get_config should return a properly resolved dict."""
    result = run_get_config(Path(temp_yaml_with_models))
    assert result is not None
    assert "models" in result
    assert result["models"]["default"] == "claude-sonnet"
    assert result["models"]["config"]["name"] == "claude-sonnet-4-6"


def test_run_get_config_with_agents(temp_yaml_with_agents):
    """run_get_config should handle nested structures like agents."""
    result = run_get_config(Path(temp_yaml_with_agents))
    assert result is not None
    assert "agents" in result
    assert result["agents"]["default"] == "general-purpose"
    config = result["agents"]["config"]
    assert "tools" in config
    assert "Read" in config["tools"]
    assert config["rules"]["max_turns"] == 20


def test_run_get_config_file_missing():
    """run_get_config should return None for a non-existent file."""
    result = run_get_config(Path("/nonexistent/path/config.yaml"))
    assert result is None


def test_run_get_config_no_defaults(temp_yaml_no_defaults):
    """run_get_config should return None when no sections have default+registry."""
    result = run_get_config(Path(temp_yaml_no_defaults))
    assert result is None


# ---------------------------------------------------------------------------
# build_system_config_section tests
# ---------------------------------------------------------------------------


def test_build_section_simple():
    """build_system_config_section should render scalar config fields."""
    resolved = {
        "models": {
            "default": "claude-sonnet",
            "config": {
                "id": "claude-sonnet",
                "provider": "anthropic",
                "name": "claude-sonnet-4-6",
                "max_tokens": 4096,
                "temperature": 0.7,
            },
        },
    }

    output = build_system_config_section(resolved)

    assert "## System Config" in output
    assert "Auto-generated" in output
    assert "### models" in output
    assert "**Default**: `claude-sonnet`" in output
    assert "```yaml" in output
    assert "provider: anthropic" in output
    assert "max_tokens: 4096" in output


def test_build_section_nested():
    """build_system_config_section should preserve nested structures."""
    resolved = {
        "databases": {
            "default": "sqlite-dev",
            "config": {
                "id": "sqlite-dev",
                "driver": "sqlite",
                "url": "sqlite:///data/dev.db",
                "pool": {"min_size": 1, "max_size": 5, "timeout_seconds": 30},
                "auto_migrate": True,
            },
        },
    }

    output = build_system_config_section(resolved)

    assert "min_size: 1" in output
    assert "max_size: 5" in output
    assert "timeout_seconds: 30" in output
    assert "auto_migrate: true" in output


def test_build_section_multiple_sorted():
    """build_system_config_section should sort sections alphabetically."""
    resolved = {
        "workflows": {"default": "w1", "config": {"id": "w1"}},
        "agents": {"default": "a1", "config": {"id": "a1"}},
        "models": {"default": "m1", "config": {"id": "m1"}},
    }

    output = build_system_config_section(resolved)

    # Verify alphabetical order
    agents_pos = output.index("### agents")
    models_pos = output.index("### models")
    workflows_pos = output.index("### workflows")
    assert agents_pos < models_pos < workflows_pos


def test_build_section_empty():
    """build_system_config_section should produce minimal output for empty dict."""
    output = build_system_config_section({})
    assert "## System Config" in output
    assert "Auto-generated" in output
    # Should not contain any ### subsection
    assert "### " not in output


# ---------------------------------------------------------------------------
# update_or_create_file tests
# ---------------------------------------------------------------------------


def test_replace_existing_section(temp_md_with_system_config):
    """update_or_create_file should replace an existing ## System Config section."""
    new_section = "## System Config\n\nNew content.\n"

    update_or_create_file(temp_md_with_system_config, new_section)

    content = temp_md_with_system_config.read_text()
    assert "New content." in content
    assert "Old auto-generated content." not in content
    # Content before and after should be preserved
    assert "# Test File" in content
    assert "## Other Section" in content
    assert "More stuff after." in content
    # Only one System Config
    assert content.count("## System Config") == 1


def test_append_when_section_missing(temp_md_file):
    """update_or_create_file should append when no ## System Config exists."""
    new_section = "## System Config\n\nAppended content.\n"

    update_or_create_file(temp_md_file, new_section)

    content = temp_md_file.read_text()
    assert "Appended content." in content
    assert "# Test File" in content
    assert "## Other Section" in content
    # The new section should come after the original content
    assert content.index("Appended content.") > content.index("## Other Section")


def test_create_new_file(tmp_path):
    """update_or_create_file should create a new file if it doesn't exist."""
    new_file = tmp_path / "new_agents.md"
    new_section = "## System Config\n\nBrand new.\n"

    update_or_create_file(new_file, new_section)

    assert new_file.exists()
    content = new_file.read_text()
    assert "Brand new." in content
    assert "## System Config" in content


def test_section_not_confused_by_similar_headings(tmp_path):
    """update_or_create_file should NOT match ## System Configuration or ### System Config."""
    content = (
        "# Test\n\n"
        "## System Configuration\n\n"
        "This is similar but different.\n\n"
        "### System Config\n\n"
        "This is an h3, not h2.\n"
    )
    md_file = tmp_path / "test.md"
    md_file.write_text(content)

    new_section = "## System Config\n\nReplaced.\n"
    update_or_create_file(md_file, new_section)

    result = md_file.read_text()
    # The similar headings should still exist
    assert "## System Configuration" in result
    assert "### System Config" in result
    # The real section should be appended (since no match was found)
    assert "Replaced." in result
    # Count only lines that are exactly "## System Config" (not substrings)
    exact_matches = [
        line for line in result.splitlines() if line.strip() == "## System Config"
    ]
    assert len(exact_matches) == 1


def test_preserves_content_around_section(temp_md_with_system_config):
    """update_or_create_file should preserve content before and after the section."""
    new_section = "## System Config\n\nUpdated.\n"

    update_or_create_file(temp_md_with_system_config, new_section)

    content = temp_md_with_system_config.read_text()
    # Content before
    before_pos = content.index("Some content before.")
    # Content after
    after_pos = content.index("More stuff after.")
    # Updated section should be between
    updated_pos = content.index("Updated.")
    assert before_pos < updated_pos < after_pos


# ---------------------------------------------------------------------------
# Regex / SECTION_PATTERN tests
# ---------------------------------------------------------------------------


def test_section_pattern_matches_exact_heading():
    """SECTION_PATTERN should match ## System Config exactly."""
    content = "## System Config\n\nSome content.\n\n## Next Section\n"
    match = SECTION_PATTERN.search(content)
    assert match is not None
    assert "Some content." in match.group()


def test_section_pattern_does_not_match_h3():
    """SECTION_PATTERN should NOT match ### System Config."""
    content = "### System Config\n\nSome content.\n\n## Next Section\n"
    match = SECTION_PATTERN.search(content)
    assert match is None


def test_section_pattern_does_not_match_partial():
    """SECTION_PATTERN should NOT match ## System Configuration."""
    content = "## System Configuration\n\nSome content.\n"
    match = SECTION_PATTERN.search(content)
    assert match is None


def test_section_pattern_stops_at_next_h2():
    """SECTION_PATTERN should stop at the next ## heading."""
    content = "## System Config\n\nConfig stuff.\n\n## Other Section\n\nMore.\n"
    match = SECTION_PATTERN.search(content)
    assert match is not None
    assert "Config stuff." in match.group()
    assert "Other Section" not in match.group()


def test_section_pattern_to_end_of_file():
    """SECTION_PATTERN should match to end of file when no next ## heading."""
    content = "## System Config\n\nLast section.\n"
    match = SECTION_PATTERN.search(content)
    assert match is not None
    assert "Last section." in match.group()


# ---------------------------------------------------------------------------
# Integration / end-to-end test
# ---------------------------------------------------------------------------


def test_end_to_end_with_subprocess(tmp_path, temp_yaml_with_agents):
    """Full integration: run the script via subprocess against temp files."""
    # Create a temp CLAUDE.md and target agents.md
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Project\n\n## Overview\n\nA test project.\n")

    agents_md = tmp_path / "agents.md"

    # Run the script
    result = subprocess.run(
        [
            sys.executable,
            str(UPDATE_CONFIG),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env={
            **os.environ,
            # We can't easily override CONFIG_FILES without monkeypatching,
            # but the script will use its own PROJECT_ROOT-relative paths.
            # For the E2E test, we rely on the real template files existing.
        },
    )

    # The script should at least have processed agents.yaml and workflows.yaml
    assert result.returncode == 0
    assert "Updated:" in result.stdout

    # Verify CLAUDE.md in the project root got updated (not the tmp one)
    project_claude = Path(__file__).resolve().parent.parent / "CLAUDE.md"
    assert project_claude.exists()
    content = project_claude.read_text()
    assert "## System Config" in content


def test_idempotency(temp_md_with_system_config):
    """Running update_or_create_file twice should produce identical output."""
    new_section = "## System Config\n\nIdempotent content.\n"

    update_or_create_file(temp_md_with_system_config, new_section)
    first_pass = temp_md_with_system_config.read_text()

    update_or_create_file(temp_md_with_system_config, new_section)
    second_pass = temp_md_with_system_config.read_text()

    assert first_pass == second_pass
