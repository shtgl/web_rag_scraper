class DefaultConfig:
  LEN_SEARCH_RESULTS = 10
  CHUNK_SIZE = 500
  CHUNK_OVERLAP = 50
  TOP_K_CHUNKS = 3
  TOP_K_URLS = 5
  LEN_MAX_TXT = 10000

  EMBED_MODEL = "all-MiniLM-L6-v2"
  LLM_BASE_URL = "http://localhost:11434"
  # LLM_MODEL = "mistral"
  LLM_MODEL = "gemma-3n"

  HEADLESS_BROWSE = False
  WAIT_TIMEOUT = 15