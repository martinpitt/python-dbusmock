# SPDX-License-Identifier: LGPL-3.0-or-later

"""Test that code examples in README.md actually work"""

# pylint does not understand pytest fixtures..
# pylint: disable=redefined-outer-name

__author__ = "Martin Pitt"
__copyright__ = """
(c) 2026 Martin Pitt <martin@piware.de>
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def readme_blocks():
    """Extract Python code blocks from README.md"""
    readme_path = Path(__file__).parent.parent / "README.md"
    return re.findall(r"```python\n(.*?)\n```", readme_path.read_text(), re.DOTALL)


def test_examples_exist(readme_blocks):
    """Verify that we found some Python code blocks"""
    assert len(readme_blocks) > 0


def test_readme_examples(readme_blocks, tmp_path):
    """Test all README examples by running them through pytest"""
    for i, code_block in enumerate(readme_blocks):
        test_file = tmp_path / f"test_readme_example_{i}.py"
        test_file.write_text(code_block)

        subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v"],
            check=True,
        )
