"""Ollama client for local LLM inference."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"


def is_ollama_running() -> bool:
    """Return True when Ollama is reachable on localhost."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def is_model_available(model: str = DEFAULT_MODEL) -> bool:
    """Return True when the requested model exists in local Ollama tags."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if response.status_code != 200:
            return False
        models = response.json().get("models", [])
        return any(model_info.get("name") == model for model_info in models)
    except requests.exceptions.RequestException:
        return False


def start_ollama_service() -> bool:
    """Start Ollama in the background when needed."""
    if is_ollama_running():
        logger.info("Ollama already running")
        return True

    logger.info("Ollama not running, attempting to start")

    try:
        preexec = os.setpgrp if os.name != "nt" else None
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=preexec,
        )
        logger.info("Started Ollama process (pid=%s)", process.pid)

        for attempt in range(20):
            time.sleep(0.5)
            if is_ollama_running():
                logger.info("Ollama ready in %.1fs", (attempt + 1) * 0.5)
                return True

        logger.error("Ollama did not become ready within 10 seconds")
        return False
    except FileNotFoundError:
        logger.error("Ollama executable not found")
        return False
    except PermissionError:
        logger.error("Permission denied while starting Ollama")
        return False
    except Exception as exc:
        logger.error("Unexpected error starting Ollama: %s", exc)
        return False


def ensure_model_available(model: str = DEFAULT_MODEL) -> bool:
    """Ensure the required Ollama model exists locally."""
    if is_model_available(model):
        logger.info("Model %s already available", model)
        return True

    logger.info("Model %s not found, pulling", model)
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode == 0:
            logger.info("Model %s pulled successfully", model)
            return True

        logger.error("Failed to pull model %s: %s", model, result.stderr.strip())
        return False
    except subprocess.TimeoutExpired:
        logger.error("Model pull timed out")
        return False
    except FileNotFoundError:
        logger.error("Ollama executable not found")
        return False
    except Exception as exc:
        logger.error("Unexpected error pulling model: %s", exc)
        return False


def summarize_meeting(transcript: str, model: str = DEFAULT_MODEL) -> Optional[str]:
    """Generate a structured markdown summary from a transcript."""
    prompt = f"""You are a meeting summarizer. Analyze the following transcript and generate a structured summary in markdown format with these exact sections:

## Key Decisions
List all concrete decisions that were made during the meeting. Include what was decided and any relevant context. If no decisions were made, write \"None identified.\"

## Discussion Topics
Summarize the main themes and topics that were discussed. Keep each topic brief but include enough context to understand what was covered. Use bullet points.

## Action Items
List all tasks, assignments, or action items mentioned. If owners or deadlines were specified, include them in the format: \"- Person to do X by Y\". If no action items were mentioned, write \"None identified.\"

## Next Steps
Capture any follow-up tasks, open questions, or items that need to be addressed in future meetings. If none were mentioned, write \"None identified.\"

CRITICAL RULES:
1. ONLY extract information explicitly stated in the transcript.
2. If no decisions/action items/next steps were mentioned, write "None identified".
3. DO NOT infer, assume, or generate placeholder content like "[Date]" or "[Person]".
4. If the transcript is unclear or garbled, note that in the summary.

---

Transcript:
{transcript}

Generate the summary now using the exact section headers above. Be concise but thorough."""

    try:
        logger.info("Sending transcript to Ollama (%s)", model)
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 2000,
                },
            },
            timeout=300,
        )
        if response.status_code != 200:
            logger.error("Ollama request failed with status %s", response.status_code)
            return None

        summary = response.json().get("response", "").strip()
        if not summary:
            logger.error("Ollama returned an empty summary")
            return None

        logger.info("Summary generated successfully")
        return summary
    except requests.exceptions.Timeout:
        logger.error("Ollama request timed out")
        return None
    except requests.exceptions.RequestException as exc:
        logger.error("Ollama request failed: %s", exc)
        return None
