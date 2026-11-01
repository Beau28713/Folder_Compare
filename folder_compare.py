"""Compare folder trees by paths, file contents, and selected metadata."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str
    size: int
    modified_ns: int
    mode: int
    digest: str | None = None
    link_target: str | None = None


@dataclass(frozen=True)
class Difference:
    path: str
    status: str
    details: str


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_folder(folder: str | os.PathLike[str]) -> dict[str, Entry]:
    """Return entries beneath a folder, raising errors rather than hiding unreadable files."""
    root = Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")

    entries: dict[str, Entry] = {}

    def visit(directory: Path) -> None:
        with os.scandir(directory) as children:
            for child in sorted(children, key=lambda item: item.name.casefold()):
                path = Path(child.path)
                relative = path.relative_to(root).as_posix()
                metadata = child.stat(follow_symlinks=False)
                mode = stat.S_IMODE(metadata.st_mode)

                if child.is_symlink():
                    entries[relative] = Entry(
                        relative,
                        "symlink",
                        metadata.st_size,
                        metadata.st_mtime_ns,
                        mode,
                        link_target=os.readlink(path),
                    )
                elif child.is_dir(follow_symlinks=False):
                    entries[relative] = Entry(
                        relative, "folder", 0, metadata.st_mtime_ns, mode
                    )
                    visit(path)
                elif child.is_file(follow_symlinks=False):
                    before = path.stat()
                    digest = _file_digest(path)
                    after = path.stat()
                    if (
                        before.st_size != after.st_size
                        or before.st_mtime_ns != after.st_mtime_ns
                    ):
                        raise OSError(f"File changed while being compared: {path}")
                    entries[relative] = Entry(
                        relative,
                        "file",
                        after.st_size,
                        after.st_mtime_ns,
                        stat.S_IMODE(after.st_mode),
                        digest=digest,
                    )
                else:
                    entries[relative] = Entry(
                        relative, "other", metadata.st_size, metadata.st_mtime_ns, mode
                    )

    visit(root)
    return entries


def compare_folders(
    first_folder: str | os.PathLike[str],
    second_folder: str | os.PathLike[str],
) -> tuple[list[Difference], int]:
    """Compare two trees and return differences plus the number of matching files."""
    first = scan_folder(first_folder)
    second = scan_folder(second_folder)

    def make_index(entries: dict[str, Entry]) -> dict[str, Entry]:
        indexed: dict[str, Entry] = {}
        for entry in entries.values():
            key = entry.path.casefold()
            if key in indexed:
                raise ValueError(
                    "Folder contains paths that differ only by letter case: "
                    f"{indexed[key].path!r} and {entry.path!r}"
                )
            indexed[key] = entry
        return indexed

    first_index = make_index(first)
    second_index = make_index(second)
    differences: list[Difference] = []
    matching_files = 0

    for key in sorted(first_index.keys() | second_index.keys()):
        left = first_index.get(key)
        right = second_index.get(key)
        if left is None:
            assert right is not None
            differences.append(
                Difference(
                    right.path, "Only in Folder 2", "Path is missing from Folder 1"
                )
            )
            continue
        if right is None:
            differences.append(
                Difference(
                    left.path, "Only in Folder 1", "Path is missing from Folder 2"
                )
            )
            continue

        if left.path != right.path:
            differences.append(
                Difference(
                    left.path,
                    "Name/case differs",
                    f"Folder 1: {left.path}; Folder 2: {right.path}",
                )
            )
        if left.kind != right.kind:
            differences.append(
                Difference(
                    left.path,
                    "Type differs",
                    f"Folder 1: {left.kind}; Folder 2: {right.kind}",
                )
            )
            continue
        if left.kind == "file":
            if left.digest != right.digest:
                differences.append(
                    Difference(
                        left.path,
                        "Contents differ",
                        f"Folder 1: {left.size} bytes; Folder 2: {right.size} bytes",
                    )
                )
            else:
                matching_files += 1
            if left.modified_ns != right.modified_ns:
                differences.append(
                    Difference(
                        left.path,
                        "Modified time differs",
                        f"Folder 1: {left.modified_ns}; Folder 2: {right.modified_ns} (nanoseconds)",
                    )
                )
            if left.mode != right.mode:
                differences.append(
                    Difference(
                        left.path,
                        "Permissions differ",
                        f"Folder 1: {left.mode:o}; Folder 2: {right.mode:o} (octal)",
                    )
                )
        elif left.kind == "symlink" and left.link_target != right.link_target:
            differences.append(
                Difference(
                    left.path,
                    "Link target differs",
                    f"Folder 1: {left.link_target}; Folder 2: {right.link_target}",
                )
            )

    return differences, matching_files
