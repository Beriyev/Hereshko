# Hereshko frontend

A frontend client for the Hereshko study and research workspace.

## Run locally

From this directory, start any static file server:

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173`.

## Included interactions

- File uploads and drag-and-drop source cards backed by `/ingest/upload`
- YouTube source ingestion backed by `/ingest/youtube`
- Auto-resizing chat composer
- Letter-by-letter rendering of responses from `/chat`
- Citation cards returned by the chat API
- Animated summary refresh
- Recursive hardcoded mind map with selectable nodes
- Mind-map prompts that can be sent back into the chat
- Responsive desktop, tablet, and mobile layouts

## Backend connection

The client expects the API at `http://localhost:8000` and uses notebook ID `nb-1`.
Override the API URL before loading `app.js` if needed:

```html
<script>window.HERESHKO_API_URL = "http://localhost:8000";</script>
```

Run the frontend with a static server from this directory:

```bash
python3 -m http.server 4173
```
