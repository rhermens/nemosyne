# Nemosyne

Nemosyne is a standalone skill curator for AI agents.

It records agent sessions, analyzes them for recurring patterns, and uses those patterns to recommend or apply improvements to agent skills. It provides skill-learning behavior similar to Hermes Agent without requiring the rest of Hermes Agent.

## Goals

- Collect structured agent sessions and skill usage data.
- Identify repeated failures, corrections, friction, and successful workflows.
- Explain why skills triggered or failed to trigger.
- Find reusable lessons across multiple sessions.
- Recommend focused improvements to existing skills.
- Apply skill changes only when explicitly authorized.
- Keep the system independent from any specific agent harness.

## Intended workflow

1. A session-ending hook calls Nemosyne's `store_session` MCP tool.
2. Nemosyne stores the session for later analysis.
3. The curator compares evidence across sessions.
4. It separates durable lessons from project-specific details.
5. It proposes changes to the relevant skills.
6. An authorized workflow reviews and applies those changes.

## Design principles

### Evidence-based curation

Skill changes must be supported by session evidence. Repeated patterns provide stronger evidence than isolated incidents.

### Recommendation before modification

Automatic analysis should produce recommendations by default. Nemosyne should modify skills only with explicit authorization.

### Minimal, targeted changes

Improvements should change the smallest relevant part of a skill. They should avoid duplicating guidance across skills.

### Privacy-aware storage

Sessions may contain source code, credentials, personal information, or confidential prompts. Storage should support sanitization, retention limits, and deletion.

### Harness independence

Session ingestion and skill updates use MCP contracts so Nemosyne can integrate with different agent harnesses.

## Current status

Nemosyne is an early prototype. It currently provides:

- A Streamable HTTP MCP server.
- A `store_session` MCP tool for completed sessions.
- Idempotent JSON session storage.
- Models for event outcomes, semantic outcomes, and skill usage.
- OpenRouter-backed LLM configuration.
- Initial support for enriching sessions with summaries and semantic outcomes.

Cross-session pattern detection and automated skill curation are not implemented yet.

## Development

This project requires Python 3.12 or newer and uses `uv`.

```bash
uv sync
uv run poe test
uv run poe check
```

Run the MCP server:

```bash
uv run daemon
```

The server exposes Streamable HTTP MCP at `http://127.0.0.1:8000/mcp`.
A session-ending hook should invoke `store_session` directly rather than asking the model to call it.
