"""Tunable configuration constants shared across the pipeline."""

# --- LLM defaults ---
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_API_TIMEOUT_SECONDS = 60.0

# --- Evaluation ---
DEFAULT_BATCH_SIZE = 8

# --- Rule extraction ---
DEDUPE_SIMILARITY_THRESHOLD = 0.86

# --- Serialization ---
JSON_INDENT = 2
