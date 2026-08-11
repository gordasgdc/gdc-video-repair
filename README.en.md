# GDC Video Repair

Free, open-source app for repairing corrupted MP4/MOV video files — the
most common case: the video card was pulled from the camera
mid-recording, or the transfer was interrupted. Uses the
**reference-file technique**, the same method used by well-known tools
like [Untrunc](https://github.com/anthwlock/untrunc).

**Presentation page**: https://gordasgdc.github.io/gdc-video-repair/
**Română**: [README.md](README.md) · **Español**: [README.es.md](README.es.md)

## Full guide, in 3 languages

Every archive in [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest)
includes a complete PDF guide (installation, how it works, examples,
troubleshooting), in Romanian, English, and Spanish. Also available
directly in [`docs/guides/`](docs/guides/).

## The problem, briefly

An MP4/MOV file has two essential parts: **`mdat`** (the raw video
data) and **`moov`** (the map for the player). The camera writes `mdat`
continuously, but only writes `moov` at the end, when you stop
recording. If you pull the card mid-recording, `moov` is missing or
incomplete — the file becomes unreadable, even though the raw video
data is often perfectly intact.

## What it can do

- Repairs H.264 and H.265 (MP4/MOV) files with missing or corrupted `moov`.
- Partially recovers files truncated mid-recording.
- Tries a quick remux first (no reference file needed) for easy cases.
- Simple GUI, or command line.

## What it doesn't do (yet)

- Single video track only — doesn't reconstruct audio if completely missing.
- H.264 and H.265 only for reference-based reconstruction.
- Doesn't repair files where the raw video data itself is corrupted at the content level, not just the header.

## Installation

### Required: FFmpeg

The app needs FFmpeg installed separately on the system — it doesn't come bundled.

```bash
# macOS
brew install ffmpeg
# Windows: download from ffmpeg.org and add to PATH
```

### macOS

Download `GDCVideoRepair.pkg` from [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest).
Double-click and follow the standard macOS installer.

### Windows

Download `GDCVideoRepair.exe` from [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest).
Double-click to run directly — no separate installation needed.

### From source (any platform, including Linux)

```bash
git clone https://github.com/gordasgdc/gdc-video-repair.git
cd gdc-video-repair
python3 src/gui.py       # graphical interface
python3 src/cli.py --help  # or command line
```

No extra Python packages needed — just the standard library and FFmpeg
installed on the system.

## Choosing a good reference file

- Filmed with the exact same camera.
- Same settings: resolution, framerate, codec.
- Content doesn't matter — any healthy clip, even a short test.

## Testing

```bash
python3 tests/run_tests.py
```

Builds real test files, corrupts them in a controlled way, runs the
repair, and verifies the result pixel by pixel against the original.

## Code structure

```
gdc-video-repair/
├── src/
│   ├── mp4_boxes.py        # MP4/MOV box structure reading
│   ├── moov_parser.py       # extracting values from moov
│   ├── sample_scanner.py    # direct sample scanning from mdat
│   ├── moov_builder.py      # building a new moov
│   ├── ffmpeg_wrapper.py    # ffmpeg/ffprobe calls
│   ├── repair_engine.py     # orchestrates the whole process
│   ├── cli.py                # command line
│   └── gui.py                # graphical interface (Tkinter)
├── build/                    # PyInstaller specs (Mac/Windows)
├── tests/run_tests.py
├── docs/                      # presentation page + PDF guides
└── LICENSE                    # MIT
```

## License

MIT — see [LICENSE](LICENSE). The app uses FFmpeg (installed separately
by the user, not bundled) as an external tool via subprocess — it
doesn't link directly against FFmpeg's libraries.

## Author

**Cristi Gordas (GDC)** — [GitHub](https://github.com/gordasgdc) · [YouTube](https://www.youtube.com/@cristigordas)
