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

1. An agent-settled hook sends the latest session snapshot to Nemosyne's HTTP API.
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

Session ingestion uses an HTTP contract so Nemosyne can integrate with different agent harnesses.

## Current status

Nemosyne is an early prototype. It currently provides:

- A FastAPI HTTP server.
- A `POST /sessions` endpoint for completed sessions.
- Idempotent updates of settled session snapshots.
- Models for event outcomes, semantic outcomes, and skill usage.
- OpenRouter-backed LLM configuration.
- Initial support for enriching sessions with summaries and semantic outcomes.
- An optional in-daemon cron job that enriches stored sessions with the configured LLM.

Cross-session pattern detection and automated skill curation are not implemented yet.

## Development

This project requires Python 3.12 or newer and uses `uv`.

```bash
uv sync
uv run poe test
uv run poe check
```

Run the HTTP server:

```bash
uv run daemon
```

The server accepts session snapshots at `http://127.0.0.1:9787/sessions`.
The same session ID is updated when a later settled snapshot arrives.

Enable the maintenance scheduler in `settings.yaml`:

```yaml
scheduler:
  enabled: true
  cron: "0 3 * * *"
  timezone: UTC
```

The cron expression uses five fields: minute, hour, day, month, and weekday.
Each run enriches incomplete session events with summaries and semantic outcomes.
Fully enriched sessions are skipped to avoid repeated LLM calls.
When enabled, stored session content is sent to the configured LLM provider.

Load the included Pi extension:

```bash
pi -e ./extensions/pi
```

The extension POSTs the active branch after each `agent_settled` event. See
[`extensions/pi/README.md`](extensions/pi/README.md) for configuration.
