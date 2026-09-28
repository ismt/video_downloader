# CLAUDE.md history

## 2026-09-28 — whole file

Rewritten to match the current `convert.py`, plus sections that make further changes easier (user request: «актуализируй», «добавь то что облегчит доработку»).

- Fixed stale facts: output dirs are `data/video`, `data/audio-convert`, `data/tmp`, `data/logs` relative to the working directory (not `C:\Users\T\Videos`); ffmpeg is searched in the winget package dir first; downloads run in a background thread; `h264`/`mkv_h264_pcm` use `TEMP_DIR`, not `Path('converted')`; the `Union` wording replaced by `X | None`.
- Added: «Checking changes» (`py_compile`, why `import convert` opens the GUI, `data/**` denied in `.claude/settings.json`), «Layout of `convert.py`», «GUI map» (control → handler → output, radio values `1`/`3`, methods not wired to the UI, window height limit), «Threading and status», «Files and directories» (table of paths, diskcache keys, log files), «Environment resolution» (ffmpeg order, GPU encoder detection), «Conventions for new code» (argv shape, method template, temp-file-then-move, single `-vf`, `-2` scaling, error beeps).
