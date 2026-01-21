import logging
import os
import shlex
import subprocess
from pathlib import Path
import glob
import shutil
import json
import sys
import platform

logging.basicConfig(level=logging.INFO)
THEROCK_BIN_DIR_STR = os.getenv("THEROCK_BIN_DIR")
if THEROCK_BIN_DIR_STR is None:
    logging.info(
        "++ Error: env(THEROCK_BIN_DIR) is not set. Please set it before executing tests."
    )
    sys.exit(1)
THEROCK_BIN_DIR = Path(THEROCK_BIN_DIR_STR)
SCRIPT_DIR = Path(__file__).resolve().parent
THEROCK_DIR = SCRIPT_DIR.parent.parent.parent

ROCJPEG_TEST_PATH = str(Path(THEROCK_BIN_DIR).parent / "share" / "rocjpeg" / "test")
if not os.path.isdir(ROCJPEG_TEST_PATH):
    logging.info(f"++ Error: tests not found in {ROCJPEG_TEST_PATH}")
    sys.exit(1)
env = os.environ.copy()

def setup_env(env):
    # catch/ctest framework
    # Linux
    #   LD_LIBRARY_PATH needs to be used
    #   tests are hardcoded to look at THEROCK_BIN_DIR or /opt/rocm/lib path
    ROCM_PATH = Path(THEROCK_BIN_DIR).resolve().parent
    env["ROCM_PATH"] = str(ROCM_PATH)
    if platform.system() == "Linux":
        HIP_LIB_PATH = Path(THEROCK_BIN_DIR).parent / "lib"
        logging.info(f"++ Setting LD_LIBRARY_PATH={HIP_LIB_PATH}")
        if "LD_LIBRARY_PATH" in env:
            env["LD_LIBRARY_PATH"] = f"{HIP_LIB_PATH}:{env['LD_LIBRARY_PATH']}"
        else:
            env["LD_LIBRARY_PATH"] = HIP_LIB_PATH
    else:
        logging.info(f"++ rocjpeg tests only supported on Linux")
        exit()


def execute_tests(env):
    
    ROCJPEG_TEST_DIR = Path(THEROCK_DIR) / "rocjpeg-test"
    cmd = [
        "mkdir",
        "-p",
        "rocjpeg-test",
    ]
    logging.info(f"++ Exec [{THEROCK_DIR}]$ {shlex.join(cmd)}")
    subprocess.run(cmd, cwd=THEROCK_DIR, check=True, env=env)

    cmd = [
        "cmake",
        ROCJPEG_TEST_PATH,
    ]
    logging.info(f"++ Exec [{ROCJPEG_TEST_DIR}]$ {shlex.join(cmd)}")
    subprocess.run(cmd, cwd=ROCJPEG_TEST_DIR, check=True, env=env)
    
    cmd = [
        "ctest",
        "--output-on-failure",
    ]
    logging.info(f"++ Exec [{ROCJPEG_TEST_DIR}]$ {shlex.join(cmd)}")
    subprocess.run(cmd, cwd=ROCJPEG_TEST_DIR, check=True, env=env)


if __name__ == "__main__":
    setup_env(env)
    execute_tests(env)