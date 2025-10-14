import subprocess


def is_ollama_running() -> bool:
    """Check if the Ollama server is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ollama serve"], capture_output=True, text=True, check=True
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False
