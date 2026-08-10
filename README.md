# GDC Video Repair

Repară fișiere video MP4/MOV corupte (de obicei: cardul scos în timpul
filmării, sau transferul întrerupt), folosind tehnica **fișierului de
referință** — aceeași metodă folosită de instrumente cunoscute precum
[Untrunc](https://github.com/anthwlock/untrunc).

## Problema, pe scurt

Un fișier MP4/MOV are două părți esențiale:
- **`mdat`** — datele video/audio brute (cadrele propriu-zise)
- **`moov`** — "harta" care spune playerului unde începe fiecare cadru în `mdat`, ce codec e folosit, rezoluția, etc.

Camera scrie `mdat` **continuu**, pe măsură ce filmează, dar scrie
`moov` abia **la final**, când oprești înregistrarea. Dacă scoți cardul
în timpul filmării (sau transferul se întrerupe), `moov` fie lipsește
complet, fie e incomplet — fișierul devine ilizibil pentru orice player,
deși datele video brute din `mdat` sunt, de multe ori, perfect intacte.

## Cum reconstruiește GDC Video Repair fișierul

1. **Încearcă întâi o remuxare rapidă** (`ffmpeg -c copy`) — rezolvă
   cazurile ușoare, unde `moov` există dar ceva minor e în neregulă
   (index prost plasat, etc.).
2. Dacă asta nu e suficient, trece la **reconstrucție bazată pe
   referință**:
   - Analizează fișierul **sănătos** de referință (filmat cu **aceeași
     cameră și aceleași setări** — rezoluție, codec, framerate) și îi
     extrage configurația exactă a codec-ului.
   - Scanează direct, byte cu byte, `mdat`-ul fișierului corupt,
     identificând limitele reale ale fiecărui cadru — inclusiv unde
     sunt cadrele-cheie (I-frames).
   - Construiește un `moov` nou, complet valid, folosind configurația
     din referință + cadrele reale găsite în fișierul corupt.
   - Scrie fișierul final: `ftyp` + `moov` (nou) + `mdat` (datele
     originale, neatinse).

Dacă fișierul e trunchiat la mijlocul filmării (nu doar `moov`-ul
lipsește, ci și `mdat`-ul e incomplet la final), unealta recuperează
**tot ce se poate recupera** până la punctul exact al corupției, și se
oprește curat acolo — nu produce cadre corupte/garbage la final.

## Ce a fost testat, concret

Nu doar teoretic — am construit fișiere de test reale (H.264 și H.265),
le-am corupt intenționat în două moduri (lipsă completă `moov`, și
trunchiere la mijlocul filmării), le-am reparat, și am comparat
**pixel cu pixel** cadre din fișierul reparat față de original:
potrivire 100%, în toate cazurile testate.

## Ce NU face (deocamdată)

- **Un singur track video** — nu reconstruiește track-uri audio dacă
  lipsesc complet (dacă fișierul corupt are și audio în `mdat`, dar
  fără `moov`, audio-ul nu e recuperat momentan — doar video).
- **Doar H.264 și H.265** — alte codec-uri video nu sunt suportate la
  reconstrucția din referință (remuxarea rapidă, la pasul 1, poate
  totuși funcționa pentru orice codec, dacă `moov`-ul exista parțial).
- **Presupune eșantioane "length-prefixed"** în `mdat` — adevărat
  pentru marea majoritate a camerelor și telefoanelor moderne (formatul
  standard MP4/MOV), dar nu universal pentru absolut orice sursă.

## Instalare

### Cerințe

- **Python 3.9+** (vine deja instalat pe majoritatea sistemelor macOS/Linux moderne; pe Windows, descarcă de pe [python.org](https://python.org))
- **FFmpeg** instalat și accesibil din linia de comandă:
  ```bash
  # macOS
  brew install ffmpeg
  # Ubuntu/Debian
  sudo apt install ffmpeg
  # Windows: descarca de pe https://ffmpeg.org/download.html si adauga in PATH
  ```

Nu sunt necesare alte pachete Python — instrumentul folosește doar
biblioteca standard.

### Descărcare

```bash
git clone https://github.com/gordasgdc/gdc-video-repair.git
cd gdc-video-repair
```

## Utilizare

### Interfață grafică (recomandat pentru începători)

```bash
python3 src/gui.py
```

Se deschide o fereastră: alegi fișierul corupt, fișierul de referință
(opțional, dar recomandat pentru cazurile grave), destinația, apeși
**Repară**.

### Linie de comandă

```bash
python3 src/cli.py --corrupt fisier_corupt.mp4 --reference fisier_sanatos.mp4 --output reparat.mp4
```

Fișierul de referință e opțional — dacă remuxarea rapidă (pasul 1)
reușește singură, nu e nevoie de el. Dacă nu îl specifici și remuxarea
rapidă eșuează, unealta îți spune clar că are nevoie de un fișier de
referință pentru reconstrucția avansată.

## Cum aleg un fișier de referință bun

- Filmat cu **exact aceeași cameră** (nu doar același model — ideal
  chiar același dispozitiv fizic).
- **Aceleași setări**: rezoluție, framerate, codec (H.264 vs H.265),
  profil de culoare, dacă sunt configurabile pe camera ta.
- Nu contează conținutul — poate fi orice clip sănătos, chiar și un
  test de câteva secunde, atâta timp cât respectă setările de mai sus.

## Depanare

**"Nu am reușit să identific eșantioane video valide"** — fișierul
corupt e probabil deteriorat și la nivelul datelor brute din `mdat`,
nu doar la header. Verifică dacă fișierul original are măcar câțiva KB
de date recognoscibile (deschide-l într-un editor hex și caută "mdat").

**"Fișierul de referință nu are un track video valid"** — asigură-te
că fișierul de referință chiar se redă normal înainte să-l folosești.

**Fișierul reparat se redă, dar imaginea e stricată/verde/artefacte** —
codec-ul sau configurația din referință nu se potrivesc exact cu
fișierul corupt (setări diferite pe cameră). Încearcă alt fișier de
referință, filmat cât mai aproape ca setări de cel corupt.

**Remuxarea rapidă (pasul 1) durează mult sau pare blocată** — pentru
fișiere foarte mari (4K/6K, multe minute), remuxarea inițială poate
dura — lasă-o să termine înainte să presupui că s-a blocat.

## Testare

În `tests/` găsești un script care construiește automat fișiere de test
(H.264 și H.265), le corupe în mod controlat (lipsă `moov`, trunchiere
parțială), rulează repararea, și verifică rezultatul pixel cu pixel
față de original. Util atât pentru validare, cât și ca exemplu de cum
se folosește motorul de reparare direct din Python.

```bash
python3 tests/run_tests.py
```

## Structura codului

```
gdc-video-repair/
├── src/
│   ├── mp4_boxes.py        # citirea structurii de "boxuri" MP4/MOV
│   ├── moov_parser.py       # extragerea valorilor din moov (stsz, stco, stsd, etc.)
│   ├── sample_scanner.py    # scanarea directa a esantioanelor din mdat
│   ├── moov_builder.py      # construirea unui moov nou, de la zero
│   ├── ffmpeg_wrapper.py    # apeluri catre ffmpeg/ffprobe (remuxare rapida + validare)
│   ├── repair_engine.py     # orchestreaza intreg procesul
│   ├── cli.py                # interfata de linie de comanda
│   └── gui.py                # interfata grafica (Tkinter)
├── tests/
│   └── run_tests.py         # teste automate, cu comparatie pixel-cu-pixel
├── requirements.txt          # gol - doar biblioteca standard Python
├── README.md
└── LICENSE                   # MIT
```

## Licență

MIT — gratuit, open-source, cod sursă complet disponibil.

## Autor

**Cristi Gordas (GDC)** — [GitHub](https://github.com/gordasgdc) · [YouTube](https://www.youtube.com/@cristigordas)
