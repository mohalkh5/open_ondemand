# LLM chat with chainlit application 

The following application provides users with a simple LLM chat interface using chainlit and Ollama. 

## How does it work?

This app launches an Ollama serve, which points to the either the user provided Ollama models or CURC's hosted models. 
Once the Ollama serve has been established, it then launches chainlit, which points to the Ollama serve using 
langchain. 

## Features

-   **Local LLM Inference**: Uses Ollama to run models locally, ensuring privacy and offline capability.
-   **Secure Authentication**: Automatic, token-based authentication tied to the system user.
-   **Persistent Chat History**: Chats are saved to a local SQLite database per user.
-   **Multi-Modal Support**: Drag-and-drop support for images (with vision-capable models like Llava) and text files.
-   **Model Management**: Automatically detects available Ollama models and their capabilities (vision support).

## Prerequisites

-   **Python 3.9+**
-   **[Ollama](https://ollama.com/)**: Must be installed and running.
    -   Pull a model to get started: `ollama pull llama3.2`

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

The application can be configured using environment variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OLLAMA_HOST` | Host and port where Ollama is running. | `localhost:11434` |
| `CHAINLIT_DATA_DIR` | Directory where chat history databases are stored. | `~/.chainlit_data` |

### Example Stand-alone Usage 
```bash
export OLLAMA_HOST="localhost:11434"
export CHAINLIT_DATA_DIR="/path/to/custom/data"
chainlit run app.py
```

## Authentication & Security

This application uses a strict, local authentication mechanism designed for shared systems:

1.  **Token Generation**: On first run, a unique secure token is generated and stored in `~/.chainlit_auth_token`.
2.  **Permissions**: This token file is created with `0o600` permissions (read/write only by the owner) to prevent other users on the system from accessing it.
3.  **Automatic Login**: The application reads this token to automatically authenticate the current system user.
4.  **Session Security**: The user's chat history is encrypted using a secret derived from this secure token.

> [!IMPORTANT]
> Do not share your `~/.chainlit_auth_token` file. It acts as your password for accessing your chat history.

## Project Structure

-   `app.py`: Main application entry point and UI logic.
-   `auth.py`: Secure authentication and token management.
-   `data_layer.py`: Custom SQLite data layer for chat persistence.
-   `models.py`: Ollama model discovery and capability detection.
-   `utils.py`: Shared utilities for file processing and permission handling.

## Usage

1.  Start Ollama: `ollama serve`
2.  Run the app: `chainlit run app.py`
3.  Open your browser to http
4.  Select a model from the settings profile and start chatting!

## License

- MIT, see `LICENSE` file.
