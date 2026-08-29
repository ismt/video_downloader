# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Personal Windows desktop tool: a Tkinter GUI (`Youtube` class) that wraps `yt-dlp.exe` and `ffmpeg.exe` to download videos/audio from YouTube and other hosts, then transcode/trim them. Single-file application: all logic lives in `convert.py`.

Run it with:

```powershell
poetry install
poetry run python convert.py
```

There are no tests, no linter config, and no CI in this repo.

## Architecture

`convert.py` has two classes plus a few module-level helpers:

- **`Converter`** — pure ffmpeg wrapper, no UI dependency. Each public method (`h264`, `av1`, `vp9`, `mp3`, `flac`, `vorbis`, `delogo`, `mkv_h264_pcm`, `to_size`, `extract_screenshot_from_video`, `add_video_preview`) builds an ffmpeg argv list and runs it through `exec_ffmpeg`. Methods are decorated with `@validate_arguments()` (Pydantic v1) for argument coercion/validation, so `Path`, `enum`, and `Union` types on parameters are enforced at call time. `TuneH264`/`PresetH264` are enums mirroring ffmpeg's `-tune`/`-preset` values for libx264.
- **`Youtube`** — owns the Tkinter window, builds the whole UI imperatively in `__init__` (radio buttons for target height, buttons wired to methods via lambdas), and drives downloads via `yt-dlp.exe` (`download_archive`, `download_any`, `download_audio`) and conversions via a `Converter` instance (`convert_to_telegram`, `convert_fast`, `convert_to_vorbis`, `convert_to_flac`). `self.root.mainloop()` runs at the end of `__init__`, so constructing `Youtube()` blocks until the window closes. The module ends with `youtube = Youtube()`, i.e. importing this module launches the GUI.
- **`diskcache.Cache('diskcache')`** (SQLite-backed, gitignored `diskcache/` dir) remembers the last-used folder/file per file picker so repeat conversions don't require renavigating — see `open_file_with_cache` and the `to_size_file_path` cache key.
- URL input comes from the clipboard (`self.tkinter_root.clipboard_get()`), not a text field — the intended flow is: copy a video URL, then click a download button.

## Hardcoded environment assumptions

These paths are baked into the code, not configurable via CLI args or env vars — if the environment differs, methods will fail at those literals rather than falling back:

- `Converter.ffmpeg_file` is resolved by `Converter.find_ffmpeg()` at construction time: it checks each path in the module-level `FFMPEG_SEARCH_PATHS` tuple, falls back to `shutil.which('ffmpeg')` (PATH lookup), and raises `FileNotFoundError` if none exist. Add new known install locations to `FFMPEG_SEARCH_PATHS` rather than hardcoding a path elsewhere.
- Some older methods (`add_video_preview`, `update_yt_dlp` params comment) instead reference a relative `../ffmpeg/bin/ffmpeg.exe` — inconsistent with `ffmpeg_file` above; check which path a given method actually uses before assuming ffmpeg's location.
- `yt_dlp_file` = `./yt-dlp.exe` — gitignored, not checked in. `Youtube.update_yt_dlp` downloads it fresh from `YT_DLP_DOWNLOAD_URL` (GitHub latest release) if missing, otherwise runs its built-in `-U` self-update.
- Download target dir: `c:/ProjectsMy/youtube/download` (used as the file-picker `initialdir` and in `file_name_format`/`file_name_format_audio`, both `../download/...`).
- Conversion output dir: `C:\Users\T\Videos\...`.

When editing conversion/download logic, keep new output paths consistent with these existing conventions rather than introducing a third convention.

## Working in this file

- `convert.py` is one file with no internal module boundaries — grep/read by method name rather than assuming a directory structure.
- ffmpeg argument lists are built as flat Python lists (`params += [...]`) and executed via `subprocess.Popen` in `exec_ffmpeg`. Follow that pattern for new conversion methods rather than shelling out differently.
- Error handling convention throughout: on ffmpeg failure, call `sound_error()` (two beeps via `winsound`) then `raise ValueError(...)`. On success, `sound_ok()` (one beep). Preserve this pattern in new code since the tool has no other user-facing failure signal.
- Several methods (`h264`, `mkv_h264_pcm`) write to a relative local file (`Path('converted')`) first, then `shutil.move` it to the final absolute path in `C:\Users\T\Videos\` — this avoids leaving partial files at the destination on failure.
