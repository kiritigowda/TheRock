# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.fspath(Path(__file__).parent.parent))

from configure_ci_path_filters import is_ci_run_required, is_test_only_change


class TestIsTestOnlyChange(unittest.TestCase):
    def test_test_script_only(self):
        paths = ["build_tools/github_actions/test_executable_scripts/test_rocprim.py"]
        self.assertTrue(is_test_only_change(paths))

    def test_test_config_only(self):
        paths = ["build_tools/github_actions/fetch_test_configurations.py"]
        self.assertTrue(is_test_only_change(paths))

    def test_test_harness_only(self):
        paths = ["build_tools/github_actions/therock_test_harness.py"]
        self.assertTrue(is_test_only_change(paths))

    def test_test_workflow_only(self):
        paths = [".github/workflows/test_artifacts.yml"]
        self.assertTrue(is_test_only_change(paths))

    def test_multiple_test_files(self):
        paths = [
            "build_tools/github_actions/test_executable_scripts/test_rocblas.py",
            "build_tools/github_actions/fetch_test_configurations.py",
            ".github/workflows/test_component.yml",
        ]
        self.assertTrue(is_test_only_change(paths))

    def test_test_files_with_skippable_files(self):
        paths = [
            "build_tools/github_actions/test_executable_scripts/test_rocprim.py",
            "docs/README.md",
        ]
        self.assertTrue(is_test_only_change(paths))

    def test_source_file_is_not_test_only(self):
        paths = ["CMakeLists.txt"]
        self.assertFalse(is_test_only_change(paths))

    def test_mixed_test_and_source_is_not_test_only(self):
        paths = [
            "build_tools/github_actions/test_executable_scripts/test_rocprim.py",
            "CMakeLists.txt",
        ]
        self.assertFalse(is_test_only_change(paths))

    def test_ci_workflow_is_not_test_only(self):
        paths = [".github/workflows/ci.yml"]
        self.assertFalse(is_test_only_change(paths))

    def test_only_skippable_files_is_not_test_only(self):
        paths = ["README.md", "docs/guide.md"]
        self.assertFalse(is_test_only_change(paths))

    def test_none_paths_is_not_test_only(self):
        self.assertFalse(is_test_only_change(None))

    def test_empty_paths_is_not_test_only(self):
        self.assertFalse(is_test_only_change([]))


class ConfigureCIPathFiltersTest(unittest.TestCase):
    def test_run_ci_if_source_file_edited(self):
        paths = ["source_file.h"]
        run_ci = is_ci_run_required(paths)
        self.assertTrue(run_ci)

    def test_dont_run_ci_if_only_markdown_files_edited(self):
        paths = ["README.md", "build_tools/README.md"]
        run_ci = is_ci_run_required(paths)
        self.assertFalse(run_ci)

    def test_dont_run_ci_if_only_experimental_files_edited(self):
        paths = ["experimental/file.h"]
        run_ci = is_ci_run_required(paths)
        self.assertFalse(run_ci)

    def test_run_ci_if_related_workflow_file_edited(self):
        paths = [".github/workflows/ci.yml"]
        run_ci = is_ci_run_required(paths)
        self.assertTrue(run_ci)

        paths = [".github/workflows/build_portable_linux_artifacts.yml"]
        run_ci = is_ci_run_required(paths)
        self.assertTrue(run_ci)

        paths = [".github/workflows/build_artifact.yml"]
        run_ci = is_ci_run_required(paths)
        self.assertTrue(run_ci)

    def test_dont_run_ci_if_unrelated_workflow_file_edited(self):
        paths = [".github/workflows/pre-commit.yml"]
        run_ci = is_ci_run_required(paths)
        self.assertFalse(run_ci)

        paths = [".github/workflows/test_jax_dockerfile.yml"]
        run_ci = is_ci_run_required(paths)
        self.assertFalse(run_ci)

    def test_run_ci_if_source_file_and_unrelated_workflow_file_edited(self):
        paths = ["source_file.h", ".github/workflows/pre-commit.yml"]
        run_ci = is_ci_run_required(paths)
        self.assertTrue(run_ci)


if __name__ == "__main__":
    unittest.main()
