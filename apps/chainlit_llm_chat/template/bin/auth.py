"""
Secure Token Authentication Module for Chainlit

Uses a private token file (~/.chainlit_auth_token) for automatic user authentication.
The token file is created with 600 permissions (read/write only by owner) to ensure security on shared systems.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional
import chainlit as cl
from utils import ensure_secure_permissions

logger = logging.getLogger(__name__)

def get_auth_token_path() -> Path:
    """Get the path to the user's private auth token."""
    return Path.home() / ".chainlit_auth_token"


def get_or_create_auth_token() -> str:
    """
    Get the auth token from file or create a new one if it doesn't exist.
    Ensures the file has 600 permissions (owner read/write only).
    """
    token_path = get_auth_token_path()
    
    if token_path.exists():
        # Verify permissions using shared utility
        ensure_secure_permissions(token_path)
        return token_path.read_text().strip()
    
    # Create new token
    token = str(uuid.uuid4())
    
    # Create file with restricted permissions
    # We use os.open to set permissions atomically at creation time
    fd = os.open(str(token_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(token)
        
    logger.info(f"Created new secure auth token at {token_path}")
    return token


def get_current_user() -> Optional[cl.User]:
    """
    Get the current user based on the private auth token.
    Returns a User object or None if authentication fails.
    """
    try:
        # Get username from environment for display
        username = os.getenv("USER", "unknown")
        
        # Get secure token for unique identification
        token = get_or_create_auth_token()
        
        return cl.User(
            identifier=username,  # Display name
            metadata={
                "username": username,
                "provider": "secure-token",
                # Use the token as the unique data ID
                "data_id": token
            }
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


@cl.header_auth_callback
def header_auth_callback(headers: dict) -> Optional[cl.User]:
    """
    Automatically authenticate users based on private token.
    """
    return get_current_user()
