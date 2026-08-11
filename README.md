# GDC Video Repair

Aplicație gratuită, open-source, pentru repararea fișierelor video MP4/MOV
corupte — cel mai frecvent caz: cardul video scos din cameră în timpul
filmării, sau transferul întrerupt. Folosește tehnica **fișierului de
referință**, aceeași metodă folosită de instrumente cunoscute precum
[Untrunc](https://github.com/anthwlock/untrunc).

**Pagina de prezentare**: https://gordasgdc.github.io/gdc-video-repair/
**English**: [README.en.md](README.en.md) · **Español**: [README.es.md](README.es.md)

## Ghid complet, în 3 limbi

Fiecare arhivă din [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest)
include și un ghid PDF complet (instalare, cum funcționează, exemple,
depanare), în română, engleză și spaniolă. Le găsești și direct în
[`docs/guides/`](docs/guides/).

## Problema, pe scurt

Un fișier MP4/MOV are două părți esențiale: **`mdat`** (datele video
brute) și **`moov`** (harta pentru player). Camera scrie `mdat`
continuu, dar scrie `moov` abia la final, când oprești înregistrarea.
Dacă scoți cardul în timpul filmării, `moov` lipsește sau e incomplet —
fișierul devine ilizibil, deși datele video brute sunt de multe ori
perfect intacte.

## Ce poate face

- Repară fișiere H.264 și H.265 (MP4/MOV) cu `moov` lipsă sau corupt.
- Recuperează parțial fișiere trunchiate la mijlocul filmării.
- Încearcă întâi o remuxare rapidă (fără fișier de referință) pentru cazurile ușoare.
- Interfață grafică simplă, sau linie de comandă.

## Ce NU face (deocamdată)

- Un singur track video — nu reconstruiește audio dacă lipsește complet.
- Doar H.264 și H.265 pentru reconstrucția din referință.
- Nu repară fișiere unde datele video brute sunt corupte la nivel de conținut, nu doar header-ul.

## Instalare

### Cerință obligatorie: FFmpeg

Aplicația are nevoie de FFmpeg instalat separat pe sistem — nu vine inclus.

```bash
# macOS
brew install ffmpeg
# Windows: descarca de pe ffmpeg.org si adauga in PATH
```

### macOS

Descarcă `GDCVideoRepair.pkg` din [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest).
Dublu-click și urmează instalatorul standard macOS.

### Windows

Descarcă `GDCVideoRepair.exe` din [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest).
Dublu-click pentru a rula direct — nu necesită instalare separată.

### Din sursă (orice platformă, inclusiv Linux)

```bash
git clone https://github.com/gordasgdc/gdc-video-repair.git
cd gdc-video-repair
python3 src/gui.py       # interfata grafica
python3 src/cli.py --help  # sau linie de comanda
```

Nu sunt necesare pachete Python suplimentare — doar biblioteca standard
și FFmpeg instalat pe sistem.

## Cum aleg un fișier de referință bun

- Filmat cu exact aceeași cameră.
- Aceleași setări: rezoluție, framerate, codec.
- Conținutul nu contează — orice clip sănătos, chiar și un test scurt.

## Testare

```bash
python3 tests/run_tests.py
```

Construiește fișiere de test reale, le corupe controlat, rulează
repararea, și verifică rezultatul pixel cu pixel față de original.

## Structura codului

```
gdc-video-repair/
├── src/
│   ├── mp4_boxes.py        # citirea structurii de boxuri MP4/MOV
│   ├── moov_parser.py       # extragerea valorilor din moov
│   ├── sample_scanner.py    # scanarea directa a esantioanelor din mdat
│   ├── moov_builder.py      # construirea unui moov nou
│   ├── ffmpeg_wrapper.py    # apeluri catre ffmpeg/ffprobe
│   ├── repair_engine.py     # orchestreaza intreg procesul
│   ├── cli.py                # linie de comanda
│   └── gui.py                # interfata grafica (Tkinter)
├── build/                    # spec-uri PyInstaller (Mac/Windows)
├── tests/run_tests.py
├── docs/                      # pagina de prezentare + ghiduri PDF
└── LICENSE                    # MIT
```

## Licență

MIT — vezi [LICENSE](LICENSE). Aplicația folosește FFmpeg (instalat
separat de utilizator, nu inclus) ca unealtă externă, prin subprocess —
nu leagă direct librăriile FFmpeg.

## Autor

**Cristi Gordas (GDC)** — [GitHub](https://github.com/gordasgdc) · [YouTube](https://www.youtube.com/@cristigordas)
