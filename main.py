from config import DefaultConfig
from logger.log_utility import setup_logger, log_stage, format_results
from text_handler import WebScraper, ContentParser, TextProcessor, TextGenerator 

CONFIG = DefaultConfig()
base_logger = setup_logger()


def main():
    user_query = input("Enter your query: ")

    base_logger.info("Pipeline started")
    base_logger.info(f"User query: {user_query}")

    searcher = WebScraper()
    parser = ContentParser()
    processor = TextProcessor()
    generator = TextGenerator()

    try:
        log_stage(base_logger, "WEB SCRAPING")
        search_results = searcher.search(user_query, CONFIG.LEN_SEARCH_RESULTS)
        base_logger.info(f"URLs collected: {len(search_results)}")
        base_logger.debug(f"URLs:\n{format_results(search_results)}")

        log_stage(base_logger, "CONTENT PARSING")
        all_chunks = []
        sources = []

        for i, url in enumerate(search_results[:CONFIG.TOP_K_URLS]):
            content = parser.fetch_and_clean(url)
            if not content:
                base_logger.warning(f"Empty content from: {url}")
                continue

            chunks = processor.chunk_text(content, CONFIG.CHUNK_SIZE, CONFIG.CHUNK_OVERLAP)
            all_chunks.extend(chunks)
            sources.extend([url] * len(chunks))

            base_logger.debug(f"URL {i+1}: {len(chunks)} chunks")

        if not all_chunks:
            base_logger.error("No content retrieved. Pipeline aborted.")
            return

        log_stage(base_logger, "EMBEDDING & RANKING")
        ranked_chunks = processor.rank_chunks(user_query, all_chunks, CONFIG.TOP_K_CHUNKS)

        for chunk in ranked_chunks:
            chunk["source"] = sources[chunk["index"]]

        for i, chunk in enumerate(ranked_chunks):
            base_logger.debug(
                f"Chunk {i+1} | Score={chunk['score']:.3f} | Source={chunk['source']}"
            )

        log_stage(base_logger, "RESPONSE GENERATION")
        answer = generator.generate_answer(user_query, ranked_chunks)

        log_stage(base_logger, "FINAL ANSWER")
        print(answer)
        base_logger.info(f"{answer}")

    finally:
        searcher.close()
        base_logger.info("Pipeline finished")


if __name__ == "__main__":
    main()

