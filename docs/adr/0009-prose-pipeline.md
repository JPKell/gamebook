# ADR 0009: Prose pipeline (versions beside the graph, keys in the environment, offline model)

**Status:** Accepted (2026-10-18)

## Context
Phase 7 generates and reviews prose with LLMs. We needed to decide:
- where prose lives relative to the undoable story graph
- how API keys are handled
- how to test a pipeline whose real outputs are non-deterministic and paid for

## Decision
- **Prose versions sit beside the graph, not inside it.**
  - `prose_version` refers to nodes and variants by id, without foreign keys.
  - Undo, which rebuilds a book's nodes from a snapshot with the same ids, neither includes
    nor rewinds prose. Prose has its own version history: draft, review, approved,
    superseded.
  - Git export carries only the approved text.
- **Staleness is a content hash** of the context the text was written for (SPEC §2.8),
  computed by the same assembler that builds prompts. That way "what the writer saw" and
  "what makes it stale" can't drift apart.
- **API keys stay in environment variables.** A provider stores the variable's *name*; the
  API reports only whether it's set. Nothing secret goes into SQLite, exports, or the call
  log.
- **An offline test model is a real provider kind** (`fake`). It is deterministic and has no
  network. Tests can queue scripted replies per role. The whole pipeline (jobs, logging,
  costs, review UI) runs end to end in pytest and Playwright without a model server. One
  opt-in smoke test (`tests/test_llm_live.py`) talks to a real endpoint when configured.
- **Synchronous client in the job thread.** Each provider has a semaphore (bounded
  concurrency), and calls get retries with backoff. Each call is logged in its own
  transaction, so a failed run still shows every call it made.

## Consequences
- Undo can restore a node whose prose has since changed; the restored node simply shows its
  latest prose. Prose history is never lost to undo.
- Computing staleness for a whole book loads the book once and assembles every approved
  variant's context: fine for hundreds of sections. It runs for the Problems panel only
  when the book has approved prose.
- Provider `headers` are stored in plain text. Don't put secrets there; use `api_key_env`.
