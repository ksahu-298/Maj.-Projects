"""Configuration for Sage chatbot."""
import importlib.util
import os

if importlib.util.find_spec("dotenv"):
    importlib.import_module("dotenv").load_dotenv()

# API keys (optional). If neither is set, Sage uses built-in empathetic responses.
# Get free keys: OpenAI (platform.openai.com), Groq (console.groq.com - free tier)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
