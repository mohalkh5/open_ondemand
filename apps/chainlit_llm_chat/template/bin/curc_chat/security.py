import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_secure_permissions(path: Path, is_dir: bool = False) -> None:
    """
    Ensure a file or directory has secure permissions (0o600 for files, 0o700 for dirs).
    Only applies to POSIX systems.
    """
    if os.name != "posix":
        return

    target_perms = 0o700 if is_dir else 0o600

    try:
        if not path.exists():
            return

        stat = path.stat()
        current_perms = stat.st_mode & 0o777

        if current_perms != target_perms:
            logger.warning(f"Fixing insecure permissions on {path}")
            path.chmod(target_perms)
    except Exception as e:
        logger.warning(f"Failed to set permissions on {path}: {e}")
