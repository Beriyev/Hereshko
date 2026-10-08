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
- Notebook selection with search, sorting, animated cards, create, and rename
- Auto-resizing chat composer
- L1 chat and streaming L2 questions/answers from `/chat/l1` and `/chat/l2`
- Citation cards returned by the chat API
- Animated summary refresh
- Recursive hardcoded mind map with selectable nodes
- Mind-map prompts that can be sent back into the chat
- Responsive desktop, tablet, and mobile layouts

## Backend connection

The client expects the API at `http://localhost:8000`. Opening the root redirects
to `notebooks.html`, which lists notebooks from `GET /notebooks`. Creating uses
`POST /notebooks`; renaming uses `PATCH /notebooks/{notebook_id}`. Selecting a card
opens `index.html?notebook_id=...` with that notebook's sources and chat.
The workspace's top-left Hereshko link returns to the selection page.

Override the API URL before loading `app.js` or `notebooks.js` on each page if needed:

```html
<script>window.HERESHKO_API_URL = "http://localhost:8000";</script>
```

Run the frontend with a static server from this directory:

```bash
python3 -m http.server 4173
```
