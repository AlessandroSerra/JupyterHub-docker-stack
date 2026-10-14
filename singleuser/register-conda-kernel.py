#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_ENVS_DIR = "/home/jovyan/work/.conda/envs"
DEFAULT_KERNEL_PREFIX = "/home/jovyan/work/.jupyter"


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def validate_name(name: str) -> None:
    pattern = r"^[A-Za-z0-9._-]+$"
    if not re.match(pattern, name):
        fail(
            "Invalid environment/kernel name. "
            "Use only letters, numbers, dots, underscores and hyphens."
        )


def get_env_dirs() -> list[Path]:
    raw = os.environ.get("CONDA_ENVS_PATH", DEFAULT_ENVS_DIR)
    return [Path(p).expanduser() for p in raw.split(os.pathsep) if p.strip()]


def find_env_path(env_name: str) -> Path:
    for env_dir in get_env_dirs():
        candidate = env_dir / env_name
        if candidate.is_dir():
            return candidate

    searched = "\n".join(f"  - {p}" for p in get_env_dirs())
    fail(
        f"Conda environment '{env_name}' not found.\n"
        f"Searched in:\n{searched}\n\n"
        f"Create it first, for example:\n"
        f"  mamba create -y -n {env_name} python=3.12 ipykernel"
    )


def check_ipykernel(env_python: Path, env_name: str) -> None:
    result = subprocess.run(
        [str(env_python), "-c", "import ipykernel"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
        fail(
            f"Environment '{env_name}' does not have ipykernel installed.\n"
            f"Install it with:\n"
            f"  mamba install -y -n {env_name} ipykernel"
        )


def register_kernel(env_name: str, kernel_name: str, display_name: str) -> None:
    env_path = find_env_path(env_name)
    env_python = env_path / "bin" / "python"

    if not env_python.exists():
        fail(f"No Python executable found at: {env_python}")

    check_ipykernel(env_python, env_name)

    kernel_prefix = Path(
        os.environ.get("JUPYTER_KERNELS_PREFIX", DEFAULT_KERNEL_PREFIX)
    ).expanduser()

    kernel_prefix.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(env_python),
        "-m",
        "ipykernel",
        "install",
        "--prefix",
        str(kernel_prefix),
        "--name",
        kernel_name,
        "--display-name",
        display_name,
    ]

    subprocess.run(cmd, check=True)

    print()
    print("Kernel registered successfully.")
    print(f"Environment:   {env_path}")
    print(f"Kernel name:   {kernel_name}")
    print(f"Display name:  {display_name}")
    print(f"Kernel prefix: {kernel_prefix}")
    print()
    print("If it does not appear immediately in JupyterLab, refresh the browser page.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register a persistent Jupyter kernel for a Conda/Mamba environment."
    )
    parser.add_argument(
        "env_name",
        help="Name of the Conda/Mamba environment, e.g. myenv",
    )
    parser.add_argument(
        "--kernel-name",
        help="Internal Jupyter kernel name. Defaults to the environment name.",
    )
    parser.add_argument(
        "--display-name",
        help='Display name shown in JupyterLab. Defaults to "Python <env_name>".',
    )

    args = parser.parse_args()

    validate_name(args.env_name)

    kernel_name = args.kernel_name or args.env_name
    display_name = args.display_name or f"Python {args.env_name}"

    validate_name(kernel_name)

    register_kernel(args.env_name, kernel_name, display_name)


if __name__ == "__main__":
    main()
