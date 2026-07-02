"""
Resolve and validate Alpine/CURC filesystem paths for chat attachments.

Users attach files by pasting absolute paths in messages (no browser upload).
Paths may live in any CURC filesystem location the user can read (including
files shared by other users under /projects/, /scratch/, etc.).
"""

import logging
import os
import re
import shlex
from pathlib import Path
from typing import List, Optional, Tuple

from curc_chat.settings import get_max_attach_files, get_max_attach_size_bytes
from curc_chat.uploads import process_paths

logger = logging.getLogger(__name__)

_FILE_COMMAND_RE = re.compile(r"^/file\s+(.+)$", re.IGNORECASE)
_HPC_PATH_PREFIXES = (
    "/home/",
    "/projects/",
    "/scratch/alpine/",
    "/pl/active/",
)


def get_username() -> str:
    return os.getenv("USER") or os.getenv("USERNAME") or "unknown"


def _is_on_curc_filesystem(path: Path) -> bool:
    """True when *path* is on a known CURC Alpine filesystem mount."""
    resolved = str(path.resolve())
    return any(
        resolved == prefix.rstrip("/") or resolved.startswith(prefix)
        for prefix in _HPC_PATH_PREFIXES
    )


def _assert_readable_file(resolved: Path, display_path: str) -> None:
    """Raise ValueError when the job process cannot read *resolved*."""
    try:
        with open(resolved, "rb"):
            pass
    except PermissionError:
        raise ValueError(
            f"Your user does not have read permissions for {display_path}."
        ) from None
    except OSError as exc:
        raise ValueError(f"Cannot read {display_path}: {exc}") from exc


def validate_hpc_path(raw_path: str, username: Optional[str] = None) -> Path:
    """Resolve *raw_path* and ensure it is a readable file on CURC filesystems."""
    username = username or get_username()

    expanded = os.path.expanduser(raw_path.strip())
    expanded = expanded.replace("${USER}", username).replace("$USER", username)
    if not expanded:
        raise ValueError("Empty file path.")

    path = Path(expanded)
    if not path.is_absolute():
        raise ValueError(f"Path must be absolute on Alpine: {raw_path}")

    resolved = path.resolve()

    if not _is_on_curc_filesystem(resolved):
        roots_display = ", ".join(_HPC_PATH_PREFIXES)
        raise ValueError(
            f"Path must be on a CURC filesystem ({roots_display}): {raw_path}"
        )

    if not resolved.exists():
        raise ValueError(f"File not found: {raw_path}")

    if resolved.is_dir():
        raise ValueError(
            f"Path is a directory, not a file: {raw_path}\n"
            f"Specify a file inside it, e.g. `{raw_path}/myfile.pdf`"
        )

    if not resolved.is_file():
        raise ValueError(f"Not a readable file: {raw_path}")

    _assert_readable_file(resolved, raw_path)

    size = resolved.stat().st_size
    max_bytes = get_max_attach_size_bytes()
    if size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValueError(f"File exceeds {max_mb} MB limit: {raw_path}")

    return resolved


def _looks_like_hpc_path(line: str) -> bool:
    if line.startswith("~/"):
        return True
    return any(line.startswith(prefix) for prefix in _HPC_PATH_PREFIXES)


def extract_paths_from_message(content: str) -> Tuple[str, List[str]]:
    """
    Pull HPC file paths from a message and return (remaining_text, raw_path_strings).

    Supported forms:
      - ``/file /projects/user/a.pdf /projects/otheruser/b.py``
      - One absolute path per line (under CURC filesystem prefixes)
    """
    if not content:
        return "", []

    raw_paths: List[str] = []
    kept_lines: List[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            kept_lines.append(line)
            continue

        file_cmd = _FILE_COMMAND_RE.match(stripped)
        if file_cmd:
            try:
                raw_paths.extend(shlex.split(file_cmd.group(1)))
            except ValueError:
                raw_paths.extend(stripped[6:].split())
            continue

        if _looks_like_hpc_path(stripped) and " " not in stripped:
            raw_paths.append(stripped)
            continue

        kept_lines.append(line)

    clean_message = "\n".join(kept_lines).strip()
    return clean_message, raw_paths


def resolve_hpc_paths(raw_paths: List[str]) -> Tuple[List[Path], List[str]]:
    """Validate paths; return (ok_paths, error_messages)."""
    max_files = get_max_attach_files()
    if len(raw_paths) > max_files:
        return [], [f"At most {max_files} files per message."]

    username = get_username()
    ok: List[Path] = []
    errors: List[str] = []

    for raw in raw_paths:
        try:
            ok.append(validate_hpc_path(raw, username))
        except ValueError as exc:
            errors.append(str(exc))
        except OSError as exc:
            errors.append(f"Cannot access {raw}: {exc}")

    return ok, errors


def process_hpc_attachments(
    content: str,
) -> Tuple[str, str, List[str], List[str], List[str]]:
    """
    Parse message content for HPC paths and load file data.

    Returns:
        (clean_user_text, additional_context, base64_images, errors, resolved_paths)
    """
    clean_message, raw_paths = extract_paths_from_message(content)
    if not raw_paths:
        return clean_message, "", [], [], []

    paths, errors = resolve_hpc_paths(raw_paths)
    logger.info(
        "HPC attachments: requested=%s valid=%s errors=%s",
        raw_paths,
        [str(p) for p in paths],
        errors,
    )
    if errors:
        return clean_message, "", [], errors, []

    if not paths:
        return clean_message, "", [], errors, []

    additional_context, images = process_paths(paths)
    return clean_message, additional_context, images, errors, [str(p) for p in paths]
