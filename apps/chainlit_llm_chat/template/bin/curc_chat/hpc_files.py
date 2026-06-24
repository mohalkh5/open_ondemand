"""
Resolve and validate Alpine/CURC filesystem paths for chat attachments.

Users attach files by pasting absolute paths in messages (no browser upload).
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


def get_allowed_roots(username: str) -> List[Path]:
    """CURC filesystem roots permitted for attachments."""
    return [
        Path(f"/home/{username}"),
        Path(f"/projects/{username}"),
        Path(f"/scratch/alpine/{username}"),
        Path("/pl/active"),
    ]


def _is_under_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


# def _assert_symlink_allowed(path: Path, resolved: Path, allowed_roots: List[Path]) -> None:
#     """
#     Future: reject symlinks that resolve outside allowed CURC roots.
#     Walk path components and ensure no symlink escapes the allowed prefix set.
#     """
#     current = Path("/")
#     for part in path.parts[1:]:
#         current = current / part
#         if current.is_symlink():
#             link_target = current.resolve()
#             if not any(_is_under_root(link_target, root) for root in allowed_roots):
#                 raise ValueError(
#                     f"Symlink {current} points outside allowed filesystem roots."
#                 )


def validate_hpc_path(raw_path: str, username: Optional[str] = None) -> Path:
    """Resolve *raw_path* and ensure it is a readable file under allowed CURC roots."""
    username = username or get_username()
    allowed_roots = get_allowed_roots(username)

    expanded = os.path.expanduser(raw_path.strip())
    if not expanded:
        raise ValueError("Empty file path.")

    path = Path(expanded)
    if not path.is_absolute():
        raise ValueError(f"Path must be absolute on Alpine: {raw_path}")

    resolved = path.resolve()

    # _assert_symlink_allowed(path, resolved, allowed_roots)

    if not any(_is_under_root(resolved, root) for root in allowed_roots):
        allowed_display = ", ".join(str(r) for r in allowed_roots)
        raise ValueError(
            f"Path is outside allowed CURC filesystem roots ({allowed_display}): {raw_path}"
        )

    if not resolved.is_file():
        raise ValueError(f"Not a file or not readable: {raw_path}")

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
      - ``/file /projects/user/a.pdf /projects/user/b.py``
      - One absolute path per line (under allowed CURC prefixes)
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


def process_hpc_attachments(content: str) -> Tuple[str, str, List[str], List[str]]:
    """
    Parse message content for HPC paths and load file data.

    Returns:
        (clean_user_text, additional_context, base64_images, errors)
    """
    clean_message, raw_paths = extract_paths_from_message(content)
    if not raw_paths:
        return clean_message, "", [], []

    paths, errors = resolve_hpc_paths(raw_paths)
    if not paths:
        return clean_message, "", [], errors

    additional_context, images = process_paths(paths)
    return clean_message, additional_context, images, errors
