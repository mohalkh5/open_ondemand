"""
Shared utilities for Chainlit application.

This module contains reusable functions for:
- Secure file permission handling
- File processing (images, text, PDFs)
"""

import os
import logging
import base64
from pathlib import Path
from typing import List, Tuple
import PyPDF2

logger = logging.getLogger(__name__)

# Common code/text file extensions
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.htm', '.css', '.scss', '.sass',
    '.json', '.yaml', '.yml', '.toml', '.xml', '.md', '.markdown', '.txt', '.rst',
    '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
    '.c', '.cpp', '.h', '.hpp', '.java', '.kt', '.go', '.rs', '.rb', '.php',
    '.sql', '.r', '.m', '.swift', '.scala', '.lua', '.pl', '.pm',
    '.dockerfile', '.makefile', '.gitignore', '.env', '.ini', '.cfg', '.conf',
    '.csv', '.log', '.vue', '.svelte'
}


def ensure_secure_permissions(path: Path, is_dir: bool = False) -> None:
    """
    Ensure a file or directory has secure permissions (0o600 for files, 0o700 for dirs).
    Only applies to POSIX systems.
    
    Args:
        path: Path to the file or directory.
        is_dir: True if path is a directory, False otherwise.
    """
    if os.name != 'posix':
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


def process_uploaded_files(elements: List[any]) -> Tuple[str, List[str]]:
    """
    Process uploaded files and return text content and image data.
    
    Args:
        elements: List of Chainlit Element objects.
        
    Returns:
        Tuple of (additional_context, list_of_base64_images)
    """
    additional_context = ""
    images = []
    
    if not elements:
        return additional_context, images
    
    for element in elements:
        mime = getattr(element, "mime", "") or ""
        name = getattr(element, "name", "") or ""
        ext = Path(name).suffix.lower()
        
        # Check if it's a code/text file by extension or MIME type
        is_code_file = ext in CODE_EXTENSIONS or (ext == '' and name.lower() in {'dockerfile', 'makefile', 'gemfile', 'rakefile'})
        is_text_mime = mime.startswith("text/") or mime in {"application/json", "application/xml"}
        
        if mime.startswith("image/"):
            images.extend(_process_image(element))
            additional_context += f"\n[Image uploaded: {name}]"
            
        elif is_code_file or is_text_mime:
            additional_context += _process_text_file(element)
            
        elif mime == "application/pdf":
            additional_context += _process_pdf(element)
    
    return additional_context, images


def _process_image(element: any) -> List[str]:
    """Extract base64 image data from an element."""
    images = []
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


def _process_text_file(element: any) -> str:
    """Extract text content from a text/json file."""
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


def _process_pdf(element: any) -> str:
    """Extract text content from a PDF file."""
    name = getattr(element, "name", "unknown")
    try:
        path = getattr(element, "path", None)
        
        if path:
            with open(path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                text = "\n".join(page.extract_text() for page in pdf_reader.pages)
                return f"\n\n--- PDF: {name} ---\n{text}\n--- End of PDF ---\n"
    except ImportError:
        return "\n[PDF support not available. Install PyPDF2 to read PDF files.]"
    except Exception as e:
        return f"\n[Error reading PDF {name}: {e}]"
    return ""
