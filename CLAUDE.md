# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Windows desktop utility for downloading YouTube videos using yt-dlp and converting media files using FFmpeg. It provides a tkinter-based GUI with buttons for various download and conversion operations.

## Commands

```bash
# Install dependencies (uses Poetry with in-project venv)
poetry install

# Run the application
python convert.py
```

## Architecture

The codebase consists of a single `convert.py` file with two main classes:

- **`Converter`**: Wraps FFmpeg operations for video/audio encoding. Supports H.264, VP9, AV1, MP3, AAC, FLAC, Vorbis conversions with various quality presets and options.

- **`Youtube`**: Handles yt-dlp operations for downloading videos/audio from YouTube and other sites. Also provides the tkinter GUI that ties everything together.

Key dependencies:
- `yt-dlp.exe` - Downloaded/updated via GUI button, stored in project root
- FFmpeg - Expected at `C:\Users\T\AppData\Local\UniGetUI\Chocolatey\lib\ffmpeg-full\tools\ffmpeg\bin\ffmpeg.exe`
- `pymediainfo` - For reading video metadata
- `diskcache` - For caching file selection paths between sessions

File outputs are hardcoded to `C:\Users\T\Videos\` and downloads go to `F:\Youtube_download`.
