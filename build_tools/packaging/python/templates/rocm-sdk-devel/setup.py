"""Main rocm-sdk-devel (OS specific)."""

import importlib.util
import os
from setuptools import setup, find_packages
import sys
import sysconfig
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


# The built package contains a pre-generated _dist_info.py file, which would
# normally be accessible at runtime. However, to make it available at
# package build time (here!), we have to dynamically import it.
def import_dist_info():
    dist_info_path = THIS_DIR / "src" / "rocm_sdk_devel" / "_dist_info.py"
    if not dist_info_path.exists():
        raise RuntimeError(f"No _dist_info.py file found: {dist_info_path}")
    module_name = "rocm_sdk_dist_info"
    spec = importlib.util.spec_from_file_location(module_name, dist_info_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


dist_info = import_dist_info()
my_package = dist_info.ALL_PACKAGES["devel"]
print(f"Loaded dist_info package: {my_package}")
packages = find_packages(where="./src")
print("Found packages:", packages)

setup(
    name=f"rocm-sdk-devel",
    version=dist_info.__version__,
    packages=packages,
    package_dir={
        "": "src",
    },
    zip_safe=False,
    include_package_data=True,
    # include_package_data=True only picks up version-controlled files.
    # The devel tarball is generated at build time, so it must be
    # explicitly listed here to be included in the wheel.
    package_data={
        "rocm_sdk_devel": ["*.tar", "*.tar.xz"],
    },
    options={
        "bdist_wheel": {
            "plat_name": os.getenv(
                "ROCM_SDK_WHEEL_PLATFORM_TAG", sysconfig.get_platform()
            ),
        },
    },
    # Wheels don't support post-install hooks, so we provide an explicit
    # command to extract the devel tarball into site-packages. Users must
    # run `rocm-sdk-devel-init` once after install to make headers, CMake
    # files, and dev libraries available for C++ compilation.
    entry_points={
        "console_scripts": [
            "rocm-sdk-devel-init=rocm_sdk_devel._cli:init",
        ],
    },
)
