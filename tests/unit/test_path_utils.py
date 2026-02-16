"""Unit tests for qa_agents.utils.path_utils – filesystem path verification."""

from __future__ import annotations

import pytest

from qa_agents.utils.path_utils import verify_path_exists


@pytest.mark.unit
class TestVerifyPathExists:
    """Verify path existence checks and edge-case handling."""

    def test_existing_directory(self, tmp_path):
        exists, resolved = verify_path_exists(str(tmp_path))

        assert exists is True
        assert resolved == str(tmp_path)

    def test_existing_file(self, sample_python_file):
        exists, resolved = verify_path_exists(str(sample_python_file))

        assert exists is True
        assert resolved == str(sample_python_file)

    def test_nonexistent_path(self, tmp_path):
        exists, resolved = verify_path_exists(str(tmp_path / "ghost"))

        assert exists is False
        assert "not found" in resolved.lower() or "Path" in resolved

    def test_sibling_lookup(self, tmp_path):
        """Verify that a child with a matching name in the parent is found."""
        target = tmp_path / "actual_file.txt"
        target.write_text("data")

        exists, resolved = verify_path_exists(str(target))

        assert exists is True

    def test_empty_string_path(self):
        exists, resolved = verify_path_exists("")

        # An empty path should either not exist or raise a controlled error
        assert isinstance(exists, bool)
        assert isinstance(resolved, str)
