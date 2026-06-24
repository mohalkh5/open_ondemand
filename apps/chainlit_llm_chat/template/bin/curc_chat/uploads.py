import base64
import logging
from pathlib import Path
from typing import Any, List, Tuple

import PyPDF2

from curc_chat.settings import get_max_pdf_extract_chars

logger = logging.getLogger(__name__)

PDF_EMPTY_MARKER = "CURC_PDF_NO_EXTRACTABLE_TEXT"

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".kt",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".sql",
    ".r",
    ".m",
    ".swift",
    ".scala",
    ".lua",
    ".pl",
    ".pm",
    ".dockerfile",
    ".makefile",
    ".gitignore",
    ".env",
    ".ini",
    ".cfg",
    ".conf",
    ".csv",
    ".log",
    ".vue",
    ".svelte",
}


IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


def process_paths(paths: List[Path]) -> Tuple[str, List[str]]:
    """Read files at server paths and return (text_context, base64_images)."""
    additional_context = ""
    images: List[str] = []

    for path in paths:
        ext = path.suffix.lower()
        name = path.name

        if ext in IMAGE_EXTENSIONS:
            images.extend(_read_image_file(path))
            additional_context += f"\n[Image attached: {path}]"

        elif (
            ext in CODE_EXTENSIONS
            or ext in {".txt", ".md", ".markdown", ".rst", ""}
            or name.lower() in {"dockerfile", "makefile", "gemfile", "rakefile"}
        ):
            additional_context += _read_text_path(path)

        elif ext == ".pdf":
            additional_context += _read_pdf_path(path)

        else:
            additional_context += (
                f"\n[Skipped unsupported file type `{ext}` for {path}. "
                "Supported: images, PDF, and text/code files.]\n"
            )

    return additional_context, images


def process_uploaded_files(elements: List[Any]) -> Tuple[str, List[str]]:
    """
    Process uploaded files and return text content and image data.

    Returns:
        Tuple of (additional_context, list_of_base64_images)
    """
    additional_context = ""
    images: List[str] = []

    if not elements:
        return additional_context, images

    for element in elements:
        mime = getattr(element, "mime", "") or ""
        name = getattr(element, "name", "") or ""
        ext = Path(name).suffix.lower()

        is_code_file = ext in CODE_EXTENSIONS or (
            ext == "" and name.lower() in {"dockerfile", "makefile", "gemfile", "rakefile"}
        )
        is_text_mime = mime.startswith("text/") or mime in {"application/json", "application/xml"}

        if mime.startswith("image/"):
            images.extend(_process_image(element))
            additional_context += f"\n[Image uploaded: {name}]"

        elif is_code_file or is_text_mime:
            additional_context += _process_text_file(element)

        elif mime == "application/pdf":
            additional_context += _process_pdf(element)

    return additional_context, images


def _read_image_file(path: Path) -> List[str]:
    images: List[str] = []
    try:
        with open(path, "rb") as f:
            images.append(base64.b64encode(f.read()).decode("utf-8"))
    except Exception as e:
        logger.warning(f"Error reading image {path}: {e}")
    return images


def _read_text_path(path: Path) -> str:
    try:
        text_content = path.read_text()
        return f"\n\n--- File: {path} ---\n{text_content}\n--- End of file ---\n"
    except Exception as e:
        return f"\n[Error reading file {path}: {e}]"


def _read_pdf_path(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            if getattr(pdf_reader, "is_encrypted", False):
                try:
                    pdf_reader.decrypt("")
                except Exception:
                    return (
                        f"\n[{PDF_EMPTY_MARKER}: `{path}` is encrypted/password-protected. "
                        "Use an unencrypted copy or export as plain text.]\n"
                    )

            page_count = len(pdf_reader.pages)
            text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages).strip()
            logger.info("PDF extract %s: pages=%d chars=%d", path, page_count, len(text))

            if not text:
                return (
                    f"\n[{PDF_EMPTY_MARKER}: `{path}` has no extractable text "
                    f"({page_count} page(s)). It may be scanned/image-only — "
                    "try OCR or a text export.]\n"
                )

            max_chars = get_max_pdf_extract_chars()
            truncated = ""
            if len(text) > max_chars:
                truncated = f"\n\n[... PDF text truncated to {max_chars} characters ...]"
                text = text[:max_chars]

            return (
                f"\n\n--- PDF: {path} ({page_count} pages, {len(text)} chars) ---\n"
                f"{text}{truncated}\n--- End of PDF ---\n"
            )
    except ImportError:
        return "\n[PDF support not available. Install PyPDF2 to read PDF files.]"
    except Exception as e:
        logger.warning("PDF read failed for %s: %s", path, e)
        return f"\n[Error reading PDF {path}: {e}]"


def _process_image(element: Any) -> List[str]:
    images: List[str] = []
    try:
        path = getattr(element, "path", None)
        content = getattr(element, "content", None)

        if path:
            with open(path, "rb") as f:
                images.append(base64.b64encode(f.read()).decode("utf-8"))
        elif content:
            images.append(base64.b64encode(content).decode("utf-8"))
    except Exception as e:
        logger.warning(f"Error processing image {getattr(element, 'name', 'unknown')}: {e}")
    return images


def _process_text_file(element: Any) -> str:
    try:
        path = getattr(element, "path", None)
        content = getattr(element, "content", None)
        name = getattr(element, "name", "unknown")

        if path:
            text_content = Path(path).read_text()
        elif content:
            text_content = content.decode("utf-8") if isinstance(content, bytes) else content
        else:
            return ""
        return f"\n\n--- File: {name} ---\n{text_content}\n--- End of file ---\n"
    except Exception as e:
        return f"\n[Error reading file {getattr(element, 'name', 'unknown')}: {e}]"


def _process_pdf(element: Any) -> str:
    name = getattr(element, "name", "unknown")
    try:
        path = getattr(element, "path", None)

        if path:
            with open(path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = "\n".join(
                    page.extract_text() or "" for page in pdf_reader.pages
                )
                return f"\n\n--- PDF: {name} ---\n{text}\n--- End of PDF ---\n"
    except ImportError:
        return "\n[PDF support not available. Install PyPDF2 to read PDF files.]"
    except Exception as e:
        return f"\n[Error reading PDF {name}: {e}]"
    return ""
