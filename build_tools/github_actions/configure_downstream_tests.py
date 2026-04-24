#!/usr/bin/env python3
# Copyright Advanced Micro Devices, Inc.
# SPDX-License-Identifier: MIT

"""
Computes which downstream tests to run based on changed artifacts.

Given a set of changed artifact names (from BUILD_TOPOLOGY.toml) or a list of
changed file paths, this script resolves all transitive downstream consumers,
maps them to test labels, and outputs per-family configuration for the CI
workflow.

Inputs (environment variables):
  - CHANGED_ARTIFACTS: comma-separated artifact names (e.g., "blas,prim")
  - CHANGED_FILES: newline-separated file paths (alternative to CHANGED_ARTIFACTS,
    used by the pull_request trigger to auto-detect affected artifacts)
  - AMDGPU_FAMILIES: comma-separated GPU families or "all" (default: "all")
  - PLATFORM: "linux" or "windows" (default: "linux")

  When both CHANGED_ARTIFACTS and CHANGED_FILES are set, CHANGED_ARTIFACTS
  takes precedence. When only CHANGED_FILES is provided, the script maps file
  paths to artifacts via: file path -> submodule -> source_set -> artifact_group
  -> artifacts.

Outputs (written to $GITHUB_OUTPUT):
  - test_labels: JSON list of test label strings (e.g., '["test:rocprim"]')
  - per_family_info: JSON array of per-family config dicts
  - has_tests: "true" or "false"
  - downstream_artifacts: JSON list of downstream artifact names
"""

import configparser
import json
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _therock_utils.build_topology import get_topology

if TYPE_CHECKING:
    from _therock_utils.build_topology import BuildTopology

from amdgpu_family_matrix import get_all_families_for_trigger_types
from github_actions_api import gha_set_output

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Repository root, used for locating .gitmodules.
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Maps BUILD_TOPOLOGY artifact names to fetch_test_configurations.py test_matrix
# keys. Each artifact maps to the test components that exercise it.
ARTIFACT_TO_TEST_LABELS: dict[str, list[str]] = {
    "blas": [
        "rocblas",
        "hipblas",
        "hipblaslt",
        "hipsolver",
        "rocsolver",
        "hipsparse",
        "rocsparse",
        "hipsparselt",
        "rocroller",
        "origami",
    ],
    "prim": ["rocprim", "hipcub", "rocthrust"],
    "rand": ["rocrand", "hiprand"],
    "fft": ["rocfft", "hipfft"],
    "sparse": ["hipsparse", "rocsparse", "hipsparselt"],
    "solver": ["hipsolver", "rocsolver"],
    "rocwmma": ["rocwmma"],
    "libhipcxx": ["libhipcxx_hipcc", "libhipcxx_hiprtc"],
    "miopen": ["miopen"],
    "composable-kernel": [],
    "hipdnn": ["hipdnn", "hipdnn-integration-tests"],
    "hipdnn-integration-tests": ["hipdnn-integration-tests"],
    "miopenprovider": ["miopenprovider"],
    "hipblasltprovider": ["hipblasltprovider"],
    "fusilliprovider": ["fusilliprovider"],
    "hipdnn-samples": ["hipdnn-samples"],
    "rccl": ["rccl"],
    "rocshmem": [],
    "rocprofiler-sdk": ["rocprofiler-sdk"],
    "rocprofiler-compute": ["rocprofiler-compute"],
    "rocprofiler-systems": ["rocprofiler-systems"],
    "aqlprofile": ["aqlprofile"],
    "core-hip": ["hip-tests"],
    "core-runtime": ["rocrtst"],
    "core-hiptests": ["hip-tests"],
    "rocrtst": ["rocrtst"],
    "amd-dbgapi": ["rocgdb", "rocr-debug-agent"],
    "rocr-debug-agent": ["rocr-debug-agent"],
    "rocgdb": ["rocgdb"],
    "rocdecode": ["rocdecode"],
    "rocjpeg": ["rocjpeg"],
    "iree-compiler": [],
}


def _parse_comma_list(value: str) -> list[str]:
    """Parse a comma-separated string into a list, stripping whitespace."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_gitmodules(gitmodules_path: Path) -> dict[str, str]:
    """Parse .gitmodules and return a mapping of submodule path -> submodule name.

    For example: {"compiler/amd-llvm": "llvm-project", "base/half": "half"}
    """
    config = configparser.ConfigParser()
    config.read(gitmodules_path)

    path_to_name: dict[str, str] = {}
    for section in config.sections():
        # Sections look like: 'submodule "llvm-project"'
        if section.startswith('submodule "') and section.endswith('"'):
            name = section[len('submodule "') : -1]
            path = config.get(section, "path", fallback=None)
            if path:
                path_to_name[path] = name

    return path_to_name


def _build_submodule_to_source_sets(
    topology: "BuildTopology",
) -> dict[str, set[str]]:
    """Build reverse mapping: submodule name -> set of source_set names."""
    result: dict[str, set[str]] = defaultdict(set)
    for source_set in topology.source_sets.values():
        for submodule in source_set.submodules:
            result[submodule.name].add(source_set.name)
    return result


def _build_source_set_to_artifact_groups(
    topology: "BuildTopology",
) -> dict[str, set[str]]:
    """Build reverse mapping: source_set name -> set of artifact_group names."""
    result: dict[str, set[str]] = defaultdict(set)
    for group in topology.artifact_groups.values():
        for ss_name in group.source_sets:
            result[ss_name].add(group.name)
    return result


def detect_changed_artifacts_from_files(
    changed_files: list[str],
    topology: "BuildTopology | None" = None,
    gitmodules_path: Path | None = None,
) -> list[str]:
    """Map changed file paths to affected artifact names.

    The mapping chain is:
        changed file path -> submodule path -> submodule name ->
        source_set -> artifact_group -> artifacts

    Files that don't map to any submodule (e.g., build_tools/, cmake/) are
    logged as warnings but do not cause all artifacts to be selected -- the
    caller should handle that policy decision.

    Returns:
        Sorted list of artifact names directly affected by the file changes.
    """
    if topology is None:
        topology = get_topology()
    if gitmodules_path is None:
        gitmodules_path = _REPO_ROOT / ".gitmodules"

    # Step 1: Parse .gitmodules for path -> name mapping
    submodule_path_to_name = _parse_gitmodules(gitmodules_path)

    # Sort submodule paths longest-first so we match the most specific path
    sorted_submodule_paths = sorted(
        submodule_path_to_name.keys(), key=len, reverse=True
    )

    # Step 2: Build reverse lookups from topology
    submodule_to_source_sets = _build_submodule_to_source_sets(topology)
    source_set_to_groups = _build_source_set_to_artifact_groups(topology)

    # Step 3: Map each changed file to artifact groups
    affected_groups: set[str] = set()
    unmapped_files: list[str] = []

    for file_path in changed_files:
        matched = False
        for submod_path in sorted_submodule_paths:
            if file_path == submod_path or file_path.startswith(submod_path + "/"):
                submod_name = submodule_path_to_name[submod_path]
                for ss_name in submodule_to_source_sets.get(submod_name, set()):
                    affected_groups.update(source_set_to_groups.get(ss_name, set()))
                matched = True
                break
        if not matched:
            unmapped_files.append(file_path)

    if unmapped_files:
        logger.info(
            "Files not mapped to any submodule (skipped): %s", unmapped_files
        )

    # Step 4: Collect artifacts from affected groups
    affected_artifacts: set[str] = set()
    for group_name in affected_groups:
        for artifact in topology.get_artifacts_in_group(group_name):
            affected_artifacts.add(artifact.name)

    return sorted(affected_artifacts)


def _get_downstream_artifacts(
    topology: "BuildTopology", artifact_name: str
) -> set[str]:
    """Get all artifacts that transitively depend on the given artifact.

    Builds a reverse-dependency index from the topology's artifact_deps,
    then performs BFS to find all transitive consumers.
    """
    if artifact_name not in topology.artifacts:
        raise ValueError(f"Artifact '{artifact_name}' not found in topology")

    # Build reverse dependency index: artifact -> set of its consumers
    reverse_deps: dict[str, set[str]] = defaultdict(set)
    for artifact in topology.artifacts.values():
        for dep in artifact.artifact_deps:
            reverse_deps[dep].add(artifact.name)

    # BFS from the changed artifact
    downstream: set[str] = set()
    queue = list(reverse_deps.get(artifact_name, set()))
    while queue:
        current = queue.pop()
        if current in downstream:
            continue
        downstream.add(current)
        queue.extend(reverse_deps.get(current, set()))

    return downstream


def get_downstream_test_labels(
    changed_artifacts: list[str], topology: "BuildTopology | None" = None
) -> tuple[list[str], set[str]]:
    """Compute test labels for changed artifacts and their downstream consumers.

    Returns:
        Tuple of (sorted test label list, set of all affected artifact names).
    """
    if topology is None:
        topology = get_topology()

    all_affected: set[str] = set(changed_artifacts)
    for artifact_name in changed_artifacts:
        try:
            downstream = _get_downstream_artifacts(topology, artifact_name)
            all_affected.update(downstream)
        except ValueError:
            logger.warning(
                "Artifact %r not found in topology, skipping downstream lookup",
                artifact_name,
            )

    # Map affected artifacts to test labels
    test_label_set: set[str] = set()
    for artifact_name in all_affected:
        if artifact_name in ARTIFACT_TO_TEST_LABELS:
            for label in ARTIFACT_TO_TEST_LABELS[artifact_name]:
                test_label_set.add(f"test:{label}")

    return sorted(test_label_set), all_affected


def build_per_family_info(
    platform: str, families: dict[str, dict] | None = None
) -> list[dict]:
    """Build per-family configuration dicts for the test matrix.

    Follows the same structure as _expand_build_config_for_platform() in
    configure_multi_arch_ci.py.
    """
    if families is None:
        families = get_all_families_for_trigger_types(["presubmit"])

    per_family_info = []
    for family_name, family_config in families.items():
        if platform not in family_config:
            continue
        platform_info = family_config[platform]
        test_runs_on = platform_info.get("test-runs-on", "")
        if not test_runs_on:
            continue
        per_family_info.append(
            {
                "amdgpu_family": platform_info["family"],
                "amdgpu_targets": ",".join(platform_info["fetch-gfx-targets"]),
                "test-runs-on": test_runs_on,
                "sanity_check_only_for_family": platform_info.get(
                    "sanity_check_only_for_family", False
                ),
            }
        )

    return per_family_info


def configure(
    changed_artifacts: list[str],
    platform: str,
    amdgpu_families_str: str,
) -> dict[str, str]:
    """Main configuration logic. Returns a dict of output key-value pairs."""
    topology = get_topology()

    test_labels, all_affected = get_downstream_test_labels(
        changed_artifacts, topology=topology
    )

    # Resolve GPU families
    if amdgpu_families_str == "all" or not amdgpu_families_str:
        all_families = get_all_families_for_trigger_types(["presubmit"])
    else:
        requested = _parse_comma_list(amdgpu_families_str)
        all_families_full = get_all_families_for_trigger_types(["presubmit"])
        all_families = {
            k: v for k, v in all_families_full.items() if k in requested
        }

    per_family_info = build_per_family_info(platform, families=all_families)
    has_tests = len(test_labels) > 0 and len(per_family_info) > 0

    downstream_only = all_affected - set(changed_artifacts)

    logger.info("Changed artifacts: %s", changed_artifacts)
    logger.info("Downstream artifacts: %s", sorted(downstream_only))
    logger.info("Test labels: %s", test_labels)
    logger.info("Per-family configs: %d families", len(per_family_info))
    logger.info("Has tests: %s", has_tests)

    return {
        "test_labels": json.dumps(test_labels),
        "per_family_info": json.dumps(per_family_info),
        "has_tests": json.dumps(has_tests),
        "downstream_artifacts": json.dumps(sorted(all_affected)),
    }


def main():
    empty_outputs = {
        "test_labels": json.dumps([]),
        "per_family_info": json.dumps([]),
        "has_tests": json.dumps(False),
        "downstream_artifacts": json.dumps([]),
    }

    changed_artifacts_str = os.environ.get("CHANGED_ARTIFACTS", "")
    changed_files_str = os.environ.get("CHANGED_FILES", "")

    if changed_artifacts_str:
        changed_artifacts = _parse_comma_list(changed_artifacts_str)
    elif changed_files_str:
        changed_files = [
            f.strip() for f in changed_files_str.splitlines() if f.strip()
        ]
        if not changed_files:
            logger.warning("CHANGED_FILES is empty, no tests to configure")
            gha_set_output(empty_outputs)
            return
        changed_artifacts = detect_changed_artifacts_from_files(changed_files)
        logger.info(
            "Auto-detected artifacts from %d changed files: %s",
            len(changed_files),
            changed_artifacts,
        )
        if not changed_artifacts:
            logger.warning(
                "No artifacts mapped from changed files, no tests to configure"
            )
            gha_set_output(empty_outputs)
            return
    else:
        logger.warning(
            "Neither CHANGED_ARTIFACTS nor CHANGED_FILES is set, "
            "no tests to configure"
        )
        gha_set_output(empty_outputs)
        return

    platform = os.environ.get("PLATFORM", "linux")
    amdgpu_families_str = os.environ.get("AMDGPU_FAMILIES", "all")

    outputs = configure(changed_artifacts, platform, amdgpu_families_str)
    gha_set_output(outputs)


if __name__ == "__main__":
    main()
