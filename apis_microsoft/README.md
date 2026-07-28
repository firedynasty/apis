# OneNote CLI — How It Works

A command-line toolkit for uploading and browsing Microsoft OneNote on macOS, using the **Microsoft Graph API** with no third-party dependencies.

---

## The Big Picture

```
Your files (.md / .txt / .html / .docx / images)
        ↓
  onenote_upload_files.sh        ← shell script (user-facing entry point)
        ↓
  onenote_signin.py              ← Python CLI (talks to the API)
        ↓
  Microsoft Graph API            ← REST API that owns your OneNote data
        ↓
  OneNote (cloud)
```

You never touch OneNote directly. Everything goes through Microsoft's **Graph API** — a single REST endpoint (`https://graph.microsoft.com/v1.0`) that gives programmatic access to your Microsoft 365 data (OneNote, Mail, Calendar, etc.).

---

## How the API Works

### 1. Register an App (one-time setup)

Before any code can talk to Microsoft, you register an app in **Azure App Registrations**. This gives you a **Client ID** — a string that tells Microsoft "this request is coming from this app."

- Redirect URI: `http://localhost` (for device code flow)
- Permission needed: `Notes.ReadWrite` (delegated — acts on your behalf)

### 2. Authenticate (OAuth 2.0 Device Code Flow)

Microsoft uses **OAuth 2.0** — you never hand your password to the script. Instead:

```
Script → POST /devicecode  →  Microsoft returns a code + URL
You    → open URL, enter code, sign in with your Microsoft account
Script → polls POST /token  →  Microsoft returns an access token + refresh token
Token  → saved to ~/.onenote_token.json
```

The **access token** is a short-lived key (~1 hour) that proves you authorized the app. The **refresh token** is long-lived and lets the script silently get a new access token without re-asking you to sign in.

```python
# onenote_signin.py — polling loop during login
while True:
    time.sleep(interval)
    r = _post(AUTH + "/token", {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": dc["device_code"],
    })
    if "access_token" in r:
        _save(r)   # writes ~/.onenote_token.json
        return
```

### 3. Every API Call Uses a Bearer Token

Once logged in, every request to Graph adds the token as a header:

```
Authorization: Bearer <access_token>
```

The script handles token expiry automatically — if the token is expired, it uses the refresh token to get a new one before making the call. A 120-second timeout is set on all requests so the script never hangs silently.

### 4. OneNote's Data Structure

OneNote is organized in three levels:

```
Notebook  →  Section  →  Page
```

The Graph API endpoints mirror this:

| What you want | API endpoint |
|---|---|
| List notebooks | `GET /me/onenote/notebooks` |
| List sections in a notebook | `GET /me/onenote/notebooks/{notebook-id}/sections` |
| List pages in a section | `GET /me/onenote/sections/{section-id}/pages` |
| Create a page | `POST /me/onenote/sections/{section-id}/pages` |
| Read a page | `GET /me/onenote/pages/{page-id}/content` |
| Update a page | `PATCH /me/onenote/pages/{page-id}/content` |

Pages are created by POSTing **HTML** to the section endpoint. Pages that include images use a **multipart request** — the HTML references images by name (`<img src="name:file.png" />`), and each image is sent as a separate binary part in the same request.

---

## The Tools

### `onenote_signin.py` — Python CLI

The core script. Uses only Python's standard library (`urllib`, `json`, `os`, `time`) — no pip installs needed.

| Command | What it does |
|---|---|
| `login` | Device code flow — opens browser, caches token |
| `notebooks` | Lists all your notebooks |
| `sections [notebook-id]` | Lists sections |
| `pages [section-id]` | Lists pages |
| `upload <file> [--title T] [--section ID]` | Uploads a single file as a new page |
| `upload-files [--title T] [--section ID] file1 file2 ...` | Bundles multiple files into one page |
| `upload-folder <folder> [--title T] [--section ID]` | Bundles an entire folder into one page |
| `download <page-id> [outfile]` | Downloads a page's HTML to a file (or stdout) |
| `update <page-id> <file>` | Replaces a page's content |

#### Supported file formats

| Format | How it's converted |
|---|---|
| `.txt` | Each line wrapped in `<p>` tags |
| `.md` | Fully converted to HTML via `mdToHtml.py` (headers, bold, links, tables, code blocks) |
| `.html` / `.htm` | Body content extracted and embedded as-is |
| `.docx` | Pandoc (best — preserves formatting) → python-docx (plain paragraphs) → textutil (plain text fallback) |
| `.jpg` / `.png` / `.gif` / `.bmp` / `.webp` | Embedded as binary image attachments in multipart request |
| hidden files (`.DS_Store` etc.) | Silently ignored |
| everything else | Printed as SKIPPED |

#### Chunking large uploads

`upload-files` and `upload-folder` automatically split content into multiple pages if the payload approaches **18 MB** (the API limit is 25 MB). Pages are named `title (1)`, `title (2)`, etc.

### `onenote_upload_files.sh` — Upload Script

The main entry point when uploading from Finder. Prompts for:
1. **Section ID** — pre-filled from clipboard
2. **Prefix** — optional, prepended to all page titles (e.g. `second_part - my_note`)

Then handles each selected item:

| What you selected | Behavior |
|---|---|
| One file | Uploaded as its own page; title = filename |
| Multiple files | Prompts for page title (pre-filled with first filename + prefix), bundled into one page via `upload-files` |
| A folder | Each folder uploaded as its own page via `upload-folder` |

Rate limiting: 2-second pause between page uploads. The API also returns `429 Too Many Requests` which triggers automatic retry with back-off.

### Finder Right-Click Integration (Automator)

`send_to_onenote_automator.txt` contains an **Automator Quick Action** (AppleScript). When installed as a macOS Quick Action:

1. Select files or folders in Finder
2. Right-click → "Send to OneNote"
3. Dialogs prompt for section ID, then prefix
4. A Terminal window opens showing upload progress

### `onenote-browse` (shell function in `~/.zshrc`)

An interactive TUI for navigating and managing your OneNote:

```
onenote-browse
  → pick a notebook number
    → pick a section
        c<n>  copy section ID to clipboard (e.g. c2 for section 2)
        ..    go back
      → pick a page
          <n>    read page as clean text in terminal
          e<n>   open page in Sublime Text for editing
          d<n>   download page as HTML file
          c      copy current section ID to clipboard
          n      create a new page
          ..     go back
```

**Reading pages**: the raw HTML from the API is stripped of all tags and rendered as clean readable text. Links are converted to `text (url)` format.

**Downloading pages**: saves the raw HTML to a file. Note — embedded images in OneNote are stored as separate authenticated resources, so `<img>` tags in the downloaded HTML will reference Graph API URLs that require your bearer token to load.

---

## First-Time Setup

```bash
# 1. Add your Azure Client ID to ~/.zshrc
export ONENOTE_CLIENT_ID=your-client-id-here

# 2. Sign in (opens browser for device code flow)
python3 onenote_signin.py login

# Token is cached at ~/.onenote_token.json — auto-refreshes from then on
```

To get a Client ID: Azure Portal → App Registrations → New Registration → API Permissions → add `Notes.ReadWrite` (delegated).

---

## Typical Workflows

### Upload a folder of mixed notes and screenshots

```bash
# 1. Get a section ID
onenote-browse
# Navigate: notebook → section → type c2 to copy section 2's ID

# 2. Right-click the folder in Finder → Send to OneNote
#    Enter prefix if desired (e.g. "second_part")
#    All .txt, .md, .docx, images bundled into one page automatically
```

### Upload selected files as one page

```bash
# Select multiple files in Finder → right-click → Send to OneNote
# Dialog asks for page title (pre-filled with first filename + prefix)
# All files bundled into one page

# Or from terminal:
python3 onenote_signin.py upload-files \
  --title "My Notes" \
  --section <section-id> \
  file1.md file2.txt screenshot.png
```

### Browse and download a page

```bash
onenote-browse
# Navigate to the page → type d3 to download page 3 as HTML
```

---

## Security Notes

- **Client ID**: stored in `ONENOTE_CLIENT_ID` environment variable — never hardcoded
- **Token file** (`~/.onenote_token.json`): lives in your home directory, never in the project — contains your OAuth tokens, keep it private
- **`.gitignore`**: excludes token files from version control
- Absolute paths in shell scripts (`/Users/...`) are personal to your machine and need updating if sharing with others
