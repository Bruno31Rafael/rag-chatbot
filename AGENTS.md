# AGENTS.md

Instructions for AI coding agents (Codex) working in this repository.
Read this file fully before making any changes.

## Project goal

A RAG chatbot called "Ask my documents". The user loads their own documents
(PDF, Markdown, text) into a vector store, then asks questions in a chat
interface. The app answers using ONLY the retrieved document passages and shows
the sources it used. If the documents do not contain the answer, it says
"I don't know" instead of guessing.

This is also a learning project. Prefer clear, simple, well-commented code over
clever code. Explain non-obvious decisions briefly.

## Tech stack (do not substitute without asking)

- Language: Python 3.11+
- Vector store: **Qdrant**, run locally with Docker. Do NOT use Chroma or any other vector store.
- Embeddings: `nomic-embed-text` via Ollama (localhost:11434). Use the prefixes "search_document: " when embedding chunks and "search_query: " when embedding questions. Read the vector size from the model, never hard-code it.
- LLM for answering: `llama3.1:latest` via Ollama. Model names for both models must be configurable in config.py (I may switch to `llama3.2:3b`). Set the context window (num_ctx) explicitly, since the Ollama default is too small for RAG prompts.
- Interface: command-line chat first. Keep the chat logic separate from the interface code so adding Streamlit later is easy.
- Dependency management: `uv` or `pip` with `requirements.txt` (pick one and stay consistent)
- Tests: `pytest`

If a library or approach seems better than one listed above, propose it and wait
for approval. Do not swap it in silently.

## Suggested structure

```
.
├── AGENTS.md
├── README.md
├── docker-compose.yml        # Qdrant
├── .env.example              # variable names only, no real values
├── data/
│   └── docs/                 # source documents (not committed if private)
├── src/
│   ├── config.py             # settings loaded from env vars
│   ├── ingest.py             # load -> chunk -> embed -> store
│   ├── retrieve.py           # question -> top matching chunks
│   ├── answer.py             # question + chunks -> grounded answer
│   └── app.py                # chat interface
├── eval/
│   ├── questions.json        # test questions with expected answers/sources
│   └── run_eval.py           # scores the system
└── tests/
```

## How to work

1. **Plan first.** For any task larger than a small fix, propose a short plan
   and wait for approval before writing code.
2. **One step at a time.** Build in this order, finishing and verifying each
   step before the next:
   1. Qdrant running in Docker + a script that confirms the connection
   2. Ingestion (load, chunk, embed, store)
   3. Retrieval
   4. Answer generation with sources and "I don't know" behavior
   5. Chat interface
   6. Evaluation script
3. **Run what you build.** After each step, run the code or tests and report
   what actually happened, including errors. Never claim something works
   without running it.
4. **Keep changes small and focused.** Do not refactor or reformat unrelated
   files. Do not add features that were not requested.
5. **Tell me how to run it.** End each task with the exact commands to run and
   test the new piece.

## RAG behavior rules

- Answers must be grounded in retrieved chunks only. Do not use the LLM's
  general knowledge to fill gaps.
- Every answer must display its sources (file name and chunk or page, if known).
- If retrieval returns nothing relevant, respond with "I don't know based on the
  provided documents."
- Make chunk size, chunk overlap, and number of retrieved chunks (top-k)
  configurable in `config.py`, not hard-coded. I will experiment with them.
- Store useful metadata with each chunk in Qdrant (source file, chunk index,
  page number when available).
- Ingestion must be safe to re-run: do not create duplicate chunks for the same
  document.

## Evaluation

- Maintain `eval/questions.json` with 10-15 questions, each with an expected
  answer or expected source document.
- `eval/run_eval.py` should report a simple score (for example: did retrieval
  return the expected source in the top-k, and did the answer contain the key
  facts).
- Before and after changing chunking, retrieval, or prompts, run the evaluation
  and tell me whether the score went up or down.

## Security and secrets

- NEVER commit API keys or secrets. Read them from environment variables.
- Keep `.env` in `.gitignore`. Maintain `.env.example` with variable names only.
- Do not print secrets in logs or error messages.
- Do not send my documents to any service other than the embedding and LLM
  providers listed in the tech stack.

## Cost awareness

- Embedding and LLM calls cost money. During development, use a small sample
  of documents (3-5 files).
- Cache embeddings where reasonable so unchanged documents are not re-embedded.
- Tell me before adding any step that makes many API calls.

## Code style

- Type hints on function signatures.
- Short docstrings on public functions.
- Small functions with a single responsibility.
- Use `logging` instead of bare `print` for anything beyond the chat output.
- Handle common failures clearly (Qdrant not running, missing API key, empty
  document) with helpful error messages.

## Testing

- Add `pytest` tests for chunking logic and any pure functions.
- Do not write tests that call paid APIs; mock them.
- Run the test suite before saying a task is done.

## Git

- Make small, logical commits with clear messages.
- Do not rewrite history or force-push.
- Never commit `data/docs/` if it contains private documents; keep it in
  `.gitignore` unless I say otherwise.

## When unsure

Ask a short clarifying question rather than guessing. If a requirement here
conflicts with a request in chat, point out the conflict and ask which to follow.