import os
import shlex
import subprocess
import shutil
import requests
from typing import Optional


class OllamaAdapter:
    """Simple adapter that calls the local Ollama CLI.

    This assumes you have `ollama` available on PATH and the model name (e.g. qwen-2.5).
    It wraps calls so you can swap implementation later.

    Enterprise-level features:
    - Temperature=0 for deterministic, consistent outputs
    - Configurable parameters via environment variables
    - Automatic retry with the HTTP API
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.0):
        # Default to a common Ollama model name; you can override with OLLAMA_MODEL env var.
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        # Temperature=0 ensures deterministic outputs for consistent extraction
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", str(temperature)))
        # quick check for ollama CLI availability; not fatal because HTTP API may be available
        self._ollama_path = shutil.which("ollama")

    def generate(self, prompt: str, temperature: Optional[float] = None) -> str:
        """Generate text using Ollama.

        ALWAYS tries the HTTP API first (supports temperature=0 for consistent results).
        Falls back to CLI only if HTTP API is unavailable.

        Args:
            prompt: The prompt to send to the model
            temperature: Override temperature for this call (default: use instance setting)

        NOTE: Uses temperature=0 by default for consistent, deterministic outputs.
        """
        temp = temperature if temperature is not None else self.temperature

        # 1) ALWAYS try HTTP API first - it supports temperature=0 for consistent results
        # Default to localhost:11434 (standard Ollama port) if not explicitly set
        http_error = None
        api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temp,
                    "num_predict": 4096,  # Allow longer outputs for complete extraction
                    "seed": 42,  # Fixed seed for reproducibility
                }
            }
            resp = requests.post(api_url, json=payload, timeout=600)  # 10 min max for HTTP
            if resp.status_code == 200:
                data = resp.json()
                # Ollama API returns response in 'response' key
                # Also check other common keys for compatibility
                for k in ("response", "text", "output", "result"):
                    if k in data and data[k]:
                        return data[k].strip()
                if isinstance(data, dict) and "data" in data:
                    return str(data["data"]).strip()
                return str(data).strip()
            else:
                http_error = RuntimeError(f"Ollama HTTP API returned status {resp.status_code}: {resp.text}")
        except requests.exceptions.RequestException as e:
            http_error = e

        # 2) Fallback to CLI if HTTP API failed
        # WARNING: CLI doesn't support temperature=0, results may be inconsistent!
        import logging
        logger = logging.getLogger("cv-chat")
        logger.warning(f"[LLM] HTTP API failed ({http_error}), falling back to CLI. Results may be inconsistent!")

        if not self._ollama_path:
            # If HTTP was attempted, include that error for debugging
            if http_error:
                raise RuntimeError(f"Ollama HTTP failure and no 'ollama' CLI found: {http_error}")
            raise RuntimeError(
                "Ollama HTTP API not configured and 'ollama' CLI not found on PATH. "
                "Ensure Ollama is running or install the CLI, or set OLLAMA_API_URL to your Ollama HTTP endpoint."
            )

        # First attempt: run using list args (recommended), but on some Windows setups
        # the ollama executable may parse args differently. If we see an unexpected
        # flag parsing error, retry with a shell-quoted command string.
        # Call ollama with the prompt as a positional argument (most Ollama installs expect: `ollama run <model> "prompt"`)
        cmd = [self._ollama_path, "run", self.model, prompt]
        try:
            # Capture raw bytes (text=False) and decode explicitly with utf-8
            # Timeout of 5 minutes (300 seconds) to prevent infinite hangs
            proc = subprocess.run(cmd, capture_output=True, text=False, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Ollama CLI timed out after 5 minutes. The prompt may be too long or the model is overloaded. Try again or use a smaller model.")
        except FileNotFoundError:
            raise RuntimeError("'ollama' CLI not found on PATH. Make sure Ollama is installed and available.")

        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip()
            # Detect flag-parsing style errors and retry with a single shell command
            if "unknown flag" in err_msg.lower() or "flag provided but not" in err_msg.lower():
                # Build a safely quoted shell command
                try:
                    # Use subprocess.list2cmdline to build a Windows-friendly command line
                    cmd_list = [self._ollama_path, "run", self.model, prompt]
                    cmd_str = subprocess.list2cmdline(cmd_list)
                    proc2 = subprocess.run(cmd_str, capture_output=True, text=False, shell=True)
                    # decode safely
                    out2 = b""
                    if proc2.stdout:
                        out2 = proc2.stdout
                    elif proc2.stderr:
                        out2 = proc2.stderr
                    decoded_out2 = out2.decode("utf-8", errors="replace").strip()
                    if proc2.returncode == 0 and decoded_out2:
                        return decoded_out2
                    # if shell retry failed, include its output in error
                    err_msg2 = decoded_out2
                    if http_error:
                        err_msg = f"HTTP error: {http_error}; CLI errors: {err_msg} | {err_msg2}"
                    else:
                        err_msg = f"CLI errors: {err_msg} | {err_msg2}"
                except Exception as e:
                    err_msg = f"CLI retry error: {e}; original: {err_msg}"
            if http_error:
                err_msg = f"HTTP error: {http_error}; CLI error: {err_msg}"
            raise RuntimeError(f"Ollama CLI error: {err_msg}")

        # decode bytes to string with utf-8 and replace errors to avoid UnicodeDecodeError on Windows
        out = ""
        try:
            if proc.stdout:
                out = proc.stdout.decode("utf-8", errors="replace").strip()
            elif proc.stderr:
                out = proc.stderr.decode("utf-8", errors="replace").strip()
        except Exception:
            out = ""
        if not out:
            raise RuntimeError("Ollama returned an empty response (no stdout). Check model availability and Ollama logs.")
        return out
