# GDC Video Repair

Aplicación gratuita y de código abierto para reparar archivos de vídeo
MP4/MOV corruptos — el caso más común: la tarjeta de vídeo se sacó de
la cámara a mitad de grabación, o la transferencia se interrumpió. Usa
la **técnica del archivo de referencia**, el mismo método que usan
herramientas conocidas como [Untrunc](https://github.com/anthwlock/untrunc).

**Página de presentación**: https://gordasgdc.github.io/gdc-video-repair/
**Română**: [README.md](README.md) · **English**: [README.en.md](README.en.md)

## Guía completa, en 3 idiomas

Cada archivo en [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest)
incluye una guía PDF completa (instalación, cómo funciona, ejemplos,
solución de problemas), en rumano, inglés y español. También disponible
directamente en [`docs/guides/`](docs/guides/).

## El problema, en resumen

Un archivo MP4/MOV tiene dos partes esenciales: **`mdat`** (los datos
de vídeo brutos) y **`moov`** (el mapa para el reproductor). La cámara
escribe `mdat` continuamente, pero solo escribe `moov` al final, cuando
detienes la grabación. Si sacas la tarjeta a mitad de grabación, `moov`
falta o está incompleto — el archivo se vuelve ilegible, aunque los
datos de vídeo brutos suelen estar perfectamente intactos.

## Qué puede hacer

- Repara archivos H.264 y H.265 (MP4/MOV) con `moov` faltante o corrupto.
- Recupera parcialmente archivos truncados a mitad de grabación.
- Prueba primero una remultiplexación rápida (sin archivo de referencia) para casos sencillos.
- Interfaz gráfica simple, o línea de comandos.

## Qué NO hace (todavía)

- Solo una pista de vídeo — no reconstruye audio si falta por completo.
- Solo H.264 y H.265 para la reconstrucción a partir de referencia.
- No repara archivos donde los propios datos de vídeo brutos están corruptos a nivel de contenido, no solo en el header.

## Instalación

### Requisito obligatorio: FFmpeg

La aplicación necesita FFmpeg instalado por separado en el sistema — no viene incluido.

```bash
# macOS
brew install ffmpeg
# Windows: descarga desde ffmpeg.org y anadelo al PATH
```

### macOS

Descarga `GDCVideoRepair.pkg` desde [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest).
Doble clic y sigue el instalador estándar de macOS.

### Windows

Descarga `GDCVideoRepair.exe` desde [Releases](https://github.com/gordasgdc/gdc-video-repair/releases/latest).
Doble clic para ejecutar directamente — no requiere instalación por separado.

### Desde el código fuente (cualquier plataforma, incluido Linux)

```bash
git clone https://github.com/gordasgdc/gdc-video-repair.git
cd gdc-video-repair
python3 src/gui.py       # interfaz grafica
python3 src/cli.py --help  # o linea de comandos
```

No se necesitan paquetes Python adicionales — solo la biblioteca
estándar y FFmpeg instalado en el sistema.

## Cómo elegir un buen archivo de referencia

- Filmado con exactamente la misma cámara.
- Los mismos ajustes: resolución, framerate, códec.
- El contenido no importa — cualquier clip sano, incluso una prueba corta.

## Pruebas

```bash
python3 tests/run_tests.py
```

Construye archivos de prueba reales, los corrompe de forma controlada,
ejecuta la reparación, y verifica el resultado píxel a píxel frente al
original.

## Estructura del código

```
gdc-video-repair/
├── src/
│   ├── mp4_boxes.py        # lectura de la estructura de boxes MP4/MOV
│   ├── moov_parser.py       # extraccion de valores de moov
│   ├── sample_scanner.py    # escaneo directo de muestras desde mdat
│   ├── moov_builder.py      # construccion de un moov nuevo
│   ├── ffmpeg_wrapper.py    # llamadas a ffmpeg/ffprobe
│   ├── repair_engine.py     # orquesta todo el proceso
│   ├── cli.py                # linea de comandos
│   └── gui.py                # interfaz grafica (Tkinter)
├── build/                    # specs de PyInstaller (Mac/Windows)
├── tests/run_tests.py
├── docs/                      # pagina de presentacion + guias PDF
└── LICENSE                    # MIT
```

## Licencia

MIT — ver [LICENSE](LICENSE). La aplicación usa FFmpeg (instalado por
separado por el usuario, no incluido) como herramienta externa vía
subprocess — no enlaza directamente con las librerías de FFmpeg.

## Autor

**Cristi Gordas (GDC)** — [GitHub](https://github.com/gordasgdc) · [YouTube](https://www.youtube.com/@cristigordas)
