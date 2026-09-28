# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Personal Windows desktop tool: a Tkinter GUI (`Youtube` class) that wraps `yt-dlp.exe` and `ffmpeg.exe` to download videos/audio from YouTube and other hosts, then transcode/trim them. Single-file application: all logic lives in `convert.py`.

Run it from the repo root (every path in the code is relative to the current working directory):

```powershell
poetry install
poetry run python convert.py
```

- Python `^3.14` (`pyproject.toml`); dependencies: `pydantic` (v2), `diskcache`, `pymediainfo`.
- There are no tests, no linter config, and no CI in this repo.
- Windows-only: `winsound`, `.exe` names, `NUL` as a null output.

## Checking changes

- Static check that does not start the app: `poetry run python -m py_compile convert.py`.
- Never `import convert` to check something: the module ends with `youtube = Youtube()`, so importing it opens the window and blocks until it closes; the import also creates the `data/*` dirs. `Converter` cannot be exercised without the GUI for the same reason.
- `.claude/settings.json` denies `Read`/`Edit` of `./data/**` (user media and logs). ffmpeg/yt-dlp output goes to the console and to `data/logs/` — to debug a failure, ask the user to paste the relevant log lines instead of reading them.

## Layout of `convert.py`

Top to bottom:

1. **Module constants** — `YT_DLP_DOWNLOAD_URL`, `WINGET_FFMPEG_PACKAGE_DIR`, `FFMPEG_SEARCH_PATHS`, `GPU_H264_ENCODERS`, the `data/` dirs (see «Files and directories»), `TELEGRAM_HEIGHTS`; helper `log_conversion`.
2. **`Converter`** — ffmpeg wrapper, no widgets of its own (but its methods open `filedialog` when `file` is not passed). Encoding methods: `h264`, `mkv_h264_pcm`, `av1`, `vp9`, `delogo`, `to_size`, `mp3`, `flac`, `vorbis`, `extract_screenshot_from_video`, `add_video_preview`. Infrastructure: `find_ffmpeg`, `detect_gpu_h264_encoder`, `exec_ffmpeg`, `exec_with_progress`, `get_video_media_info` (first video track from `pymediainfo`), nested `TuneH264`/`PresetH264` enums (libx264 `-tune`/`-preset` values) and the `ConvertResult` dataclass.
3. **`Youtube`** — builds the whole UI imperatively in `__init__` and ends it with `self.root.mainloop()`, so constructing `Youtube()` blocks until the window closes. Download methods (`download_archive`, `download_any`, `download_audio`, `update_yt_dlp`, `download_yt_dlp`), conversion handlers (`convert_to_telegram`, `convert_fast`, `convert_to_mp3`, `convert_to_vorbis`, `convert_to_flac`), `create_link`, `open_file_with_cache`, status plumbing.
4. **Module helpers** — `sound_error`, `sound_ok`, `filter_float` (MediaInfo returns frame rate as a string, possibly with a decimal comma).

`convert.py` has no internal module boundaries — grep/read by method name.

## GUI map

Radio buttons set `selected_size` (a `StringVar`): heights `1080`…`144`, `1` = «Высота не указывать», `3` = «Создать ссылку». `3` is a mode, not a height: every handler that reads `selected_size` must treat `1` and `3` explicitly.

| Control | Handler | Does | Output |
| :--- | :--- | :--- | :--- |
| «Скачать ютуб» | `exec_button` → `download_archive` | yt-dlp `bestvideo[height<=H]+bestaudio`, subs, chapters, playlists; `1` = cap 1080; `3` = `create_link` (symlink via two pickers) | `data/download/` |
| «Скачать ютуб аудио» | `download_audio` | yt-dlp `bestaudio --extract-audio` | `data/download/` |
| «Скачать ролик с любого хостнга» | `download_any` | yt-dlp `best[height=H]` (exact height) | `data/download/` |
| «Конвертация Телеграм» | `convert_to_telegram` | `Converter.h264`: crf 24, `veryslow`, tune from the combobox, trim from «Начало видео»/«Конец видео», preview frame | `data/video/*.mp4` |
| «Конвертация быстро» | `convert_fast` | `Converter.mkv_h264_pcm(crf=30, ultrafast)` | `data/video/<stem>_fast.mkv` |
| «Конвертация MP3/Vorbis/FLAC» | `convert_to_mp3` / `convert_to_vorbis` / `convert_to_flac` | `Converter.mp3` / `vorbis` / `flac` | `data/audio-convert/` |
| «Обновить yt-dlp» | `update_yt_dlp` | download if missing, else `yt-dlp -U` | `./yt-dlp.exe` |

- Entries «Время для превью» (`preview_time`), «Начало видео» (`edit_start_video_time`), «Конец видео» (`edit_end_video_time`) and the tune combobox are used only by `convert_to_telegram`.
- `convert_to_telegram` asks for the video, then for a preview image; cancelling the second picker extracts a frame at `preview_time`. It scales only when the chosen height is in `TELEGRAM_HEIGHTS` and below the source height.
- `vp9`, `av1`, `delogo`, `to_size`, `add_video_preview` are not wired to any control. They are run by temporarily editing the body of `convert_fast` (its commented-out calls show this usage).
- URL input comes from the clipboard (`self.tkinter_root.clipboard_get()`, must start with `http`), not a text field: copy a video URL, then click a download button.
- Adding a control: `ttk.Button(self.root, ...)` + `.pack(fill='x', padx=padx, pady=pady)` in `__init__` before `mainloop()`. The window is fixed at 500×750 and not resizable — new widgets may end up below the visible area; raise `window_height` when adding.

## Threading and status

- Downloads run in a daemon thread (`_run_download_in_thread` → `Converter.exec_with_progress`, which streams yt-dlp lines). The worker never touches widgets: it puts `('status', text)` / `('done', (ok, error_message))` into `self._status_queue`; `_poll_status_queue` applies them on the Tk thread every 100 ms and beeps / shows a `messagebox` on `done`.
- Conversions run synchronously on the Tk thread — the window freezes until ffmpeg exits. To make a long operation non-blocking, reuse the queue pattern above.
- The `status` property setter writes to `label_status` directly — call it only from the Tk thread.
- An exception raised inside a button callback does not close the app: Tk prints the traceback to the console and the status label stays at «Старт». Watch the console when testing.

## Files and directories

All relative to the current working directory:

| Path | Constant / owner | Purpose |
| :--- | :--- | :--- |
| `data/download/` | `DOWNLOAD_DIR` | yt-dlp output (`file_name_format`, `file_name_format_audio`), default `initialdir` of file pickers |
| `data/video/` | `VIDEOS_OUTPUT_DIR` | video conversions; not created by code — exists through the tracked `data/video/.gitkeep` |
| `data/audio-convert/` | `AUDIO_OUTPUT_DIR` | audio conversions |
| `data/tmp/` | `TEMP_DIR` | intermediate files (`converted.<ext>`, preview `.ts` parts) |
| `data/logs/` | `LOGS_DIR` | `conversion.log` (output of `exec_ffmpeg` calls, OK/FAIL lines of `mkv_h264_pcm`), `convert-to-telegram.log` (main encode of `convert_to_telegram`) |
| `diskcache/` | `diskcache.Cache('diskcache')` | last-used file/dir per picker |
| `yt-dlp.exe` | `Youtube.yt_dlp_file` | gitignored; downloaded from `YT_DLP_DOWNLOAD_URL` |

- `AUDIO_OUTPUT_DIR`, `TEMP_DIR`, `DOWNLOAD_DIR`, `LOGS_DIR` are created on import. `data/*` is gitignored except `data/video/.gitkeep`.
- Output names are built from the input stem plus encoding parameters (e.g. `h264`: `<stem>__<crf>_<width>_<height>-<tune>.mp4`) and written with `-y`: a rerun with the same parameters overwrites.
- `diskcache` keys: `convert_to_telegram`, `convert_to_telegram_preview` (file paths, via `open_file_with_cache`), `to_size_file_path` (a directory, in `Converter.to_size`). Both classes open their own `Cache` on the same dir.

## Environment resolution

- `Converter.find_ffmpeg()` runs in `Converter.__init__`, i.e. at startup: newest `ffmpeg-*-full_build` under `WINGET_FFMPEG_PACKAGE_DIR` (winget `Gyan.FFmpeg`), then `FFMPEG_SEARCH_PATHS`, then `shutil.which('ffmpeg')`, else `FileNotFoundError`. Add new known install locations to `FFMPEG_SEARCH_PATHS` rather than hardcoding a path elsewhere.
- `download_archive` and `download_audio` pass the resolved ffmpeg dir to yt-dlp as `--ffmpeg-location`; `download_any` does not.
- GPU H.264: `detect_gpu_h264_encoder` tries `GPU_H264_ENCODERS` in order (NVENC → QSV → AMF) with a real 5-frame test encode and caches the result on the instance. `{crf}` in the flag templates is replaced with the quality value. Only `mkv_h264_pcm(use_gpu=True)` uses it; `convert_fast` does not pass `use_gpu`, so it encodes with libx264.

## Conventions for new code

- ffmpeg argv is a flat list built with `params += [...]`, first element `self.ffmpeg_file.as_posix() + ' '` (every method does this; the trailing space is a legacy quirk Windows tolerates — keep it identical to the neighbours rather than fixing it in one place). `Path` objects go into the list as-is.
- Run through `exec_ffmpeg` (synchronous, returns `bool`, prints and logs output). For line-by-line progress use `exec_with_progress(args, on_line=...)`.
- Shape of a `Converter` method: `@validate_call`; `file: Path | None = None`, falling back to `fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())`; output into one of the `*_OUTPUT_DIR` constants; `-y`; `print(params)`; on failure `sound_error()` then `raise ValueError(...)`; return `ConvertResult(in_file=..., out_file=...)` (audio methods, `delogo`; the rest still return a bare `Path` or nothing).
- `@validate_call` coerces arguments at call time, so pass enum members (`self.converter_obj.PresetH264.veryslow`); a name from the GUI goes through `TuneH264[name]`.
- Write to `TEMP_DIR / 'converted'` + suffix first and `shutil.move` to the final path only on success (as `mkv_h264_pcm` does), so a failed run leaves no partial file at the destination. The temp name is fixed — safe only while conversions run one at a time; running them in threads needs unique temp names.
- `-ss`/`-to` are placed after `-i` (output seeking): frame-accurate, but ffmpeg decodes from the start of the file.
- One `-vf` per command: ffmpeg keeps only the last `-vf`/`-filter:v`, so combine filters with a comma (`scale=...,fps=...`). Scale with `-2` for the free dimension (`scale=-2:{height}`): libx264 with `yuv420p` rejects odd sizes.
- Error signalling: the tool has no other user-facing failure signal, so keep it. `Converter` uses the module-level `sound_error()` (two beeps) / `sound_ok()` (one beep); `Youtube` has its own `self.sound_error()`, which also sets the status to «Ошибка».
- UI strings and code comments are in Russian; this file and `README.md` are in English.
