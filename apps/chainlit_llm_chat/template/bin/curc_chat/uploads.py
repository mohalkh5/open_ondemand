import base64
import logging
from pathlib import Path
from typing import Any, List, Tuple

import PyPDF2

logger = logging.getLogger(__name__)

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
