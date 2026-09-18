# Nemosyne Pi extension

This extension sends the active Pi session branch to Nemosyne after each `agent_settled` event.
It includes user and assistant text messages, plus tool names, timestamps, and success or failure outcomes.
Thinking, images, and other non-text message blocks are not sent.

## Run

Start Nemosyne:

```bash
uv run daemon
```

Load the extension:

```bash
pi -e ./extensions/pi
```

Set `NEMOSYNE_URL` when the server does not use `http://127.0.0.1:9787`:

```bash
NEMOSYNE_URL=http://127.0.0.1:9000 pi -e ./extensions/pi
```

Pi waits up to five seconds for each request. A failed request shows a warning and does not interrupt the session.

## Development

```bash
npm install
npm test
npm run check
```
