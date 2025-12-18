import re
import time
import ollama
import requests
from logger.log_utility import setup_logger
from bs4 import BeautifulSoup
from config import DefaultConfig
from sentence_transformers import SentenceTransformer, util

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


CONFIG = DefaultConfig()
base_logger = setup_logger()

class WebScraper:
    def __init__(self, headless=CONFIG.HEADLESS_BROWSE):
      self.options = Options()
      if headless:
          self.options.add_argument("--headless")
      self.options.add_argument("--window-size=1920,1080")
      self.options.add_argument("--disable-blink-features=AutomationControlled")
      self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
      self.options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36")
      self.options.page_load_strategy = 'eager'
      self.driver = webdriver.Chrome(options=self.options)
      self.driver.implicitly_wait(10)

    def search(self, query, num_results=10):
        base_logger.info(f"Searching Google for URLs: '{query}'")

        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        self.driver.get(search_url)
        time.sleep(3)

        urls = set()
        anchors = self.driver.find_elements(By.CSS_SELECTOR, "a")

        BLOCKED_DOMAINS = [
            "google.com",
            "instagram.com",
            "linkedin.com",
            "facebook.com",
            "twitter.com",
            "youtube.com",
            "maps.google",
            "webcache.googleusercontent"
        ]

        for a in anchors:
            href = a.get_attribute("href")
            if not href or not href.startswith("http"):
                continue

            # Remove anchors and tracking fragments
            href = href.split("#")[0]

            # Block noisy / non-content domains
            if any(domain in href for domain in BLOCKED_DOMAINS):
                continue

            urls.add(href)

            if len(urls) >= num_results:
                break

        base_logger.info(f"Collected {len(urls)} URLs")
        return list(urls)


    def close(self):
        self.driver.quit()

class ContentParser:
    @staticmethod
    def fetch_and_clean(url):
        base_logger.info(f"Fetching content from: {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n+", "\n", text)

            return text[:CONFIG.LEN_MAX_TXT]

        except Exception:
            return None
        
class TextProcessor:
    def __init__(self):
        self.embedder = SentenceTransformer(CONFIG.EMBED_MODEL)

    def chunk_text(self, text, chunk_size, overlap):
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size - overlap):
            chunks.append(" ".join(words[i:i + chunk_size]))
            if i + chunk_size >= len(words):
                break

        return chunks

    def rank_chunks(self, query, chunks, top_k):
        query_emb = self.embedder.encode(query, convert_to_tensor=True)
        chunk_embs = self.embedder.encode(chunks, convert_to_tensor=True)

        scores = util.cos_sim(query_emb, chunk_embs)[0]
        top = scores.topk(k=min(top_k, len(scores)))

        return [
            {
                "text": chunks[idx],
                "score": score.item(),
                "index": idx.item()
            }
            for score, idx in zip(top.values, top.indices)
        ]

class TextGenerator:
    def __init__(self):
        self.model = CONFIG.LLM_MODEL
        base_logger.info(f"Initialized local LLM: {self.model}")
    
    def generate_answer(self, query, context_chunks):
        base_logger.info("Generating answer with local LLM")
        
        context_with_sources = ""
        for i, chunk in enumerate(context_chunks):
            context_with_sources += f"--- CHUNK {i+1} ---\n{chunk['text']}\n\n"
        
        prompt = f"""You are an expert AI assistant. Using ONLY the context information provided below, answer the user's query. 

        USER QUERY: {query}

        CONTEXT INFORMATION:
        {context_with_sources}

        CRITICAL INSTRUCTIONS:
        1. You must base your answer ONLY on the provided context
        2. If the context contains relevant information, you MUST use it to answer
        3. You must base your answer ONLY on the provided context from these specific sources
        4. You must cite the actual source URL for each piece of information using this format: (Source: [full URL])
        5. If multiple sources support the same point, cite the most relevant one
        6. If the context doesn't contain the answer, say "The provided sources don't contain specific information about this."
        7. Keep your answer concise and factual
        8. Reference the source material where appropriate

        Answer:"""
        
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            answer = response['response']

            base_logger.info("LLM response generated successfully")
            return answer
        except Exception as e:
            base_logger.info(f"Error generating answer: {str(e)}", "ERROR")
            return "I encountered an error while generating an answer."

