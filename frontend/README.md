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
- GraphWeaver mind maps generated from a selected notebook source, with top-down branches, expand/collapse controls, zoom, and drag-to-pan
- Mind-map prompts that can be sent back into the chat
- Animated map reveals and branch movement; scrollwheel navigation, Ctrl/Command + wheel zoom, and dragging from the canvas or a node
- Testweaver source selection, objective MCQs, and up to three subjective questions
- Answer progress, scores out of 10, MCQ explanations, and subjective improvement points with expected answers
- Animated Testweaver modal, mode selector, loading dots and skeletons, staggered question reveals, selection states, and feedback; reduced-motion support
- Responsive desktop, tablet, and mobile layouts

## Backend connection

The client expects the API at `http://localhost:8000`. Opening the root redirects
to `notebooks.html`, which lists notebooks from `GET /notebooks`. Creating uses
`POST /notebooks`; renaming uses `PATCH /notebooks/{notebook_id}`. Selecting a card
opens `index.html?notebook_id=...` with that notebook's sources and chat.
GraphWeaver sends `POST /notebooks/{notebook_id}/mindmap` with a JSON `document_id`
and displays the returned nodes. Generated maps are cached in the current browser
session until the page reloads; Regenerate requests a fresh map. The selected
source must have persisted extracted content on the backend.
The workspace's top-left Hereshko link returns to the selection page.

Testweaver calls `POST /testweaver/objective/generate` or
`POST /testweaver/subjective/generate` with query parameters `document_id`,
`notebook_id`, and `number_of_questions`. Objective responses are question lists;
subjective responses are `[question, expected_answer]` pairs. The frontend keeps
them in memory until the page reloads and displays feedback after submission.

Objective checking uses `POST /testweaver/objective/submit` with JSON
`question_list` and `provided_answers_list` (exact option text). Subjective
checking uses `POST /testweaver/subjective/submit` with JSON `pairs_list` and
`answer_list`. Both return a result list. Failed checks preserve written answers
and selected choices for retrying. Reopening Testweaver preserves the current test.

Browser checks use fixture responses without calling Gemini:

```powershell
.venv/Scripts/python.exe -m tests.test_testweaver_frontend
```

Override the API URL before loading `app.js` or `notebooks.js` on each page if needed:

```html
<script>window.HERESHKO_API_URL = "http://localhost:8000";</script>
```

Run the frontend with a static server from this directory:

```bash
python3 -m http.server 4173
```
