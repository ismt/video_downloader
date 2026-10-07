# CLAUDE.md history

## 2026-09-28 — whole file

Rewritten to match the current `convert.py`, plus sections that make further changes easier (user request: «актуализируй», «добавь то что облегчит доработку»).

- Fixed stale facts: output dirs are `data/video`, `data/audio-convert`, `data/tmp`, `data/logs` relative to the working directory (not `C:\Users\T\Videos`); ffmpeg is searched in the winget package dir first; downloads run in a background thread; `h264`/`mkv_h264_pcm` use `TEMP_DIR`, not `Path('converted')`; the `Union` wording replaced by `X | None`.
- Added: «Checking changes» (`py_compile`, why `import convert` opens the GUI, `data/**` denied in `.claude/settings.json`), «Layout of `convert.py`», «GUI map» (control → handler → output, radio values `1`/`3`, methods not wired to the UI, window height limit), «Threading and status», «Files and directories» (table of paths, diskcache keys, log files), «Environment resolution» (ffmpeg order, GPU encoder detection), «Conventions for new code» (argv shape, method template, temp-file-then-move, single `-vf`, `-2` scaling, error beeps).

## 2026-10-07 — GUI map, Threading and status, Files and directories, Conventions for new code

Updated after changes to `Converter.h264` and `convert_to_telegram` (user request: sound as close to the original as possible, remove the 33 ms shift caused by the prepended preview).

- GUI map: the «Конвертация Телеграм» row now says the preview is overlaid on frame 0 and AAC audio is copied (other codecs → AAC 256k); new bullet on the overlay, explicit `-map [v] -map 0:a:0?` (first audio track only, subtitles dropped) and `copy_video` + preview raising `ValueError`.
- Threading and status: `_download_worker` added to the download chain (the nested `worker` became a method).
- Files and directories: preview `.ts` parts removed from `data/tmp/` — the concat step no longer exists.
- Conventions for new code: `h264` is an exception to output seeking — it seeks on input so the overlay's `n=0` is the first output frame.

## 2026-10-07 — Layout of `convert.py`, Checking changes, Conventions for new code

Brought in line with the current `convert.py` (user request: «актуализируй CLAUDE.md»).

- Layout of `convert.py`: `get_audio_media_info` added to the `Converter` infrastructure list.
- Checking changes: new bullet — `convert.py` passes the external ruff rule set except an `I001` false positive on `import diskcache` (the `diskcache/` cache folder is taken for a first-party package).
- Conventions for new code: new bullets on full type annotations (return annotations are not validated by `@validate_call`, newly annotated parameters are) and on AAC encoding (default `twoloop`, no `-aac_coder fast`, copy AAC sources); the temp-file-then-move bullet now names `h264` as well.

## 2026-10-07 — GUI map, Conventions for new code (libx264 lookahead threads)

Added after `h264` got a `lookahead_threads` parameter (user request: check whether the Telegram conversion uses the whole machine; chosen value 5).

- GUI map: the «Конвертация Телеграм» row lists `lookahead_threads=5`.
- Conventions for new code: new bullet on libx264 parallelism — single-threaded lookahead with `veryslow`, x264's height-based thread caps, `lookahead_threads` clipping, `-x264opts opencl` being a no-op on this laptop.
- Measured on a 305 s 720p60 source encoded to 360p (variants of `lookahead-threads`): 1 — 200.7 s; 2 — 162.3 s, −0.05 dB SSIM; 3 — 147.1 s, −0.10 dB; 5 — 142.3 s, −0.08 dB, file +0.6%. Chosen 5; rejected 2 (best quality of the faster variants) and keeping 1.
