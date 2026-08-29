# video_downloader

Personal Windows desktop tool. Tkinter GUI wraps `yt-dlp.exe` and `ffmpeg.exe` to download video/audio from YouTube (and other hosts), then transcode/trim it. Single-file app — all logic in `convert.py`.

## Requirements

- Windows
- Python + Poetry
- `ffmpeg.exe` (see `FFMPEG_SEARCH_PATHS` in `convert.py`)
- `yt-dlp.exe` — auto-downloaded on first run if missing (`Youtube.update_yt_dlp`)

## Run

```powershell
poetry install
poetry run python convert.py
```

No tests, no linter config, no CI in this repo.

## Architecture

See `CLAUDE.md` for class layout, hardcoded paths, and conventions to follow when editing `convert.py`.

## Feed full source into an agent's context

For an agent with file tools (Claude Code and similar), just ask it to read everything tracked by git (this naturally skips anything in `.gitignore`):

```
Read every file tracked by git in this repo (run `git ls-files --cached --others --exclude-standard` to list them, this already excludes .gitignore) into context, then answer: <your question>
```
