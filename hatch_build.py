from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple, override

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging import tags
from packaging.version import Version

CRATE_NAME = "graph"
TARGET_DIR = Path("vapoursynth/plugins/graph")


class CPU(NamedTuple):
    name: str
    suffix: str
    disable: str = ""


class Target(NamedTuple):
    prefix: str
    ext: str
    cpus: list[CPU] | None = None


x86_64_CPUS = [
    CPU("x86-64", ""),
    CPU("haswell", ".avx2"),
    CPU("znver4", ".zn4", disable="sse4a"),
]

TARGETS = {
    "linux": {
        "x86_64": Target("lib", ".so", x86_64_CPUS),
        "aarch64": Target("lib", ".so"),
    },
    "windows": {"amd64": Target("", ".dll", x86_64_CPUS)},
    "darwin": {
        "x86_64": Target("lib", ".dylib", x86_64_CPUS[:-1]),
        "arm64": Target("lib", ".dylib"),
    },
}


class CustomHook(BuildHookInterface[Any]):
    @override
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{next(tags.platform_tags())}"

        uname = platform.uname()
        target = TARGETS[uname.system.lower()][uname.machine.lower()]

        TARGET_DIR.mkdir(parents=True, exist_ok=True)

        # Inject VS plugin version
        version_pkg = Version(self.metadata.version)
        env = os.environ.copy()
        env["GRAPH_VERSION_MAJOR"] = str(version_pkg.major)
        env["GRAPH_VERSION_MINOR"] = str(version_pkg.minor)

        # Multiple target support
        if os.environ.get("GRAPH_MULTIPLE_TARGET", "").lower() in ["true", "1"] and target.cpus:
            print("Building multiple targets...", file=sys.stderr)

            host_target_triple = get_host_target_triple()

            for cpu in target.cpus:
                rust_flags = [f"-C target-cpu={cpu.name}"]

                if cpu.disable:
                    rust_flags.append(f" -C target-feature=-{cpu.disable}")

                env = env.copy()
                env["RUSTFLAGS"] = " ".join(rust_flags)
                built_target_dir = Path(f"target/{cpu.name}")
                subprocess.run(
                    ["cargo", "build", "--release", "--target", host_target_triple, "--target-dir", built_target_dir],
                    check=True,
                    env=env,
                )

                built = built_target_dir / host_target_triple / "release" / f"{target.prefix}{CRATE_NAME}{target.ext}"
                shutil.copy2(built, TARGET_DIR / Path(built.name).with_suffix(cpu.suffix + built.suffix))

            # Write a manifest to ensure instruction set-based loading works as desired
            # https://github.com/vapoursynth/vapoursynth/discussions/1196
            (TARGET_DIR / "manifest.vs").write_text(f"[VapourSynth Manifest V1]\n{target.prefix}{CRATE_NAME}\n")
        else:
            # Build for *this* machine
            env["RUSTFLAGS"] = "-C target-cpu=native"

            subprocess.run(["cargo", "build", "--release"], check=False, env=env)

            built = Path("target") / "release" / f"{target.prefix}{CRATE_NAME}{target.ext}"
            shutil.copy2(built, TARGET_DIR)

    @override
    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        shutil.rmtree(TARGET_DIR, ignore_errors=True)


def get_host_target_triple() -> str:
    result = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError("Could not determine host target triple from `rustc -vV`")
