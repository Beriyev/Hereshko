## Run locally

Open Docker Desktop, wait until it is running, then run this from PowerShell:

```powershell
.\start.ps1
```

The script starts Weaviate, the FastAPI backend, and the frontend, then opens the app at `http://localhost:4173`.

## YouTube authentication

Public videos are downloaded using yt-dlp's default clients without reading
browser cookies. The project installs the JavaScript solver via
`yt-dlp[default]`; Deno must also be installed for full YouTube support.
Leave `YT_PLAYER_CLIENT` empty to use the maintained yt-dlp defaults.
Configured cookies are tried only if the initial request needs authentication.

If YouTube requests sign-in, select the browser with your signed-in session in `.env`:

```dotenv
YT_COOKIES_BROWSER=opera-gx
```

Supported sources are `chrome`, `edge`, `firefox`, `brave`, `chromium`, `opera`,
`opera-gx`, `vivaldi`, `whale`, and `safari` (macOS). Opera GX uses its standard
Windows profile path automatically. Other browsers use yt-dlp's default profile.
Restart the backend after changing these settings. Close the browser if its
cookie database is locked; OS encryption may prevent extraction even from a
supported browser.

Use `YT_COOKIES_PROFILE` to select a specific profile name or path. Optional
`YT_COOKIES_KEYRING` selects a Linux Chromium keyring, and
`YT_COOKIES_CONTAINER` selects a Firefox container.

For other browsers, or if direct extraction fails, set `YT_COOKIES_FILE` to an
exported Netscape-format cookie file. This takes precedence over browser
extraction. Keep cookie files private and outside version control. Empty cookie
settings leave ingestion unauthenticated. Cookies must be available on the
machine running the backend, not merely in the browser displaying the frontend.
