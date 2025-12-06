# LLM chat with chainlit application 

The following application provides users with a simple LLM chat interface using chainlit and Ollama. 

## How does it work?

This app launches an Ollama serve, which points to the either the user provided Ollama models or CURC's hosted models. 
Once the Ollama serve has been established, it then launches chainlit, which points to the Ollama serve using 
langchain. 

## License

- MIT, see `LICENSE` file.
