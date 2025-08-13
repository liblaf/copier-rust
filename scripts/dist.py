# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "cappa",
#     "pydantic",
# ]
# ///

import functools
import os
import platform
import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import Annotated, Self

import cappa
import pydantic


class Target(pydantic.BaseModel):
    kind: list[str]
    name: str


class Package(pydantic.BaseModel):
    name: str
    targets: list[Target]


class Metadata(pydantic.BaseModel):
    packages: list[Package]
    target_directory: Path

    @classmethod
    def load(cls) -> Self:
        process: subprocess.CompletedProcess[bytes] = subprocess.run(
            ["cargo", "metadata", "--no-deps", "--format-version", "1"],
            stdout=subprocess.PIPE,
            check=True,
        )
        return cls.model_validate_json(process.stdout)

    @property
    def targets(self) -> Generator[str]:
        for package in self.packages:
            for target in package.targets:
                if "bin" in target.kind:
                    yield target.name


def copy(
    artifact: str | os.PathLike[str],
    dist_dir: str | os.PathLike[str],
    triple: str | None = None,
) -> None:
    artifact = Path(artifact)
    dist_dir = Path(dist_dir)
    if triple is None:
        triple = host_tuple()
    dst_filename: str = f"{artifact.stem}-{triple}{artifact.suffix}"
    dst: Path = dist_dir / dst_filename
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact, dst)
    print(f"'{artifact}' -> '{dst}'")


@functools.cache
def host_tuple() -> str:
    process: subprocess.CompletedProcess[str] = subprocess.run(
        ["rustc", "--print", "host-tuple"],
        stdout=subprocess.PIPE,
        check=True,
        text=True,
    )
    return process.stdout.strip()


@cappa.command
class Command:
    dist: Annotated[Path, cappa.Arg(short=True, long=True, default=Path("dist"))]

    def __call__(self) -> None:
        metadata: Metadata = Metadata.load()
        for target in metadata.targets:
            filename: str = target
            if platform.system() == "Windows":
                filename += ".exe"
            if (artifact := metadata.target_directory / "release" / filename).exists():
                copy(artifact, self.dist)
            for artifact in metadata.target_directory.glob(f"*/release/{filename}"):
                triple: str = artifact.parts[-3]
                copy(artifact, self.dist, triple=triple)


if __name__ == "__main__":
    cappa.invoke(Command)
