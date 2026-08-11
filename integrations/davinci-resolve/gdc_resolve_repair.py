#!/usr/bin/env python3
"""
gdc_resolve_repair.py — integrare DaVinci Resolve pentru GDC Video Repair.

Rulare: din Resolve, Workspace > Scripts > gdc_resolve_repair (pune fisierul
in folderul de scripturi Resolve — vezi cale mai jos), sau din linia de
comanda cu Resolve deja deschis.

Flux:
  1. Ia clipul (sau clipurile) selectate in Media Pool.
  2. Pentru fiecare, cere un fisier de referinta (primul clip "sanatos"
     gasit in acelasi bin, cu aceeasi rezolutie/codec — sau il ceri
     explicit printr-un dialog simplu).
  3. Ruleaza GDC Video Repair (ca subproces, folosind cli.py) pe fiecare.
  4. Daca reparatia reuseste, importa automat fisierul reparat inapoi
     in Media Pool, in acelasi bin, langa originalul.

Cai standard pentru modulul de scripting Resolve:
  macOS:   /Library/Application Support/Blackmagic Design/DaVinci Resolve/
           Developer/Scripting/Modules/
  Windows: %PROGRAMDATA%/Blackmagic Design/DaVinci Resolve/Support/
           Developer/Scripting/Modules/
  Linux:   /opt/resolve/Developer/Scripting/Modules/
"""

from __future__ import annotations
import os
import sys
import subprocess
import tempfile

# --- Configureaza aici calea catre GDC Video Repair, daca nu e in PATH ---
GDC_REPAIR_CLI = os.environ.get("GDC_REPAIR_CLI", "python3")
GDC_REPAIR_SCRIPT = os.environ.get(
    "GDC_REPAIR_SCRIPT",
    os.path.expanduser("~/gdc-video-repair/src/cli.py"),
)

VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v")


def _setup_resolve_module_path():
    """Adauga in sys.path modulul de scripting Resolve, in functie de OS,
    daca nu e deja accesibil (scriptul ruleaza in afara consolei Resolve)."""
    if sys.platform == "darwin":
        modules_path = ("/Library/Application Support/Blackmagic Design/"
                         "DaVinci Resolve/Developer/Scripting/Modules/")
    elif sys.platform == "win32":
        modules_path = os.path.join(
            os.environ.get("PROGRAMDATA", ""), "Blackmagic Design",
            "DaVinci Resolve", "Support", "Developer", "Scripting", "Modules",
        )
    else:
        modules_path = "/opt/resolve/Developer/Scripting/Modules/"
    if modules_path not in sys.path:
        sys.path.append(modules_path)


def get_resolve():
    try:
        import DaVinciResolveScript as dvr_script
    except ImportError:
        _setup_resolve_module_path()
        import DaVinciResolveScript as dvr_script
    resolve = dvr_script.scriptapp("Resolve")
    if resolve is None:
        raise RuntimeError(
            "Nu m-am putut conecta la DaVinci Resolve. Ruleaza scriptul "
            "din interiorul Resolve (Workspace > Scripts), sau porneste "
            "Resolve inainte sa rulezi scriptul separat."
        )
    return resolve


def get_selected_clips(media_pool):
    """Intoarce clipurile video selectate in Media Pool. Resolve nu are
    o functie directa 'GetSelectedClips' universala pe toate versiunile,
    asa ca folosim folderul curent si filtram dupa ce e marcat ca
    'selected' in interfata, cu fallback pe folderul curent intreg daca
    API-ul instalat nu expune selectia individuala."""
    current_folder = media_pool.GetCurrentFolder()
    clips = current_folder.GetClipList()
    selected = [c for c in clips if getattr(c, "GetClipProperty", None) and
                _is_video_file(c.GetClipProperty("File Path") or "")]
    return selected


def _is_video_file(path: str) -> bool:
    return path.lower().endswith(VIDEO_EXTENSIONS)


def _find_reference_candidate(media_pool_item, all_clips) -> str | None:
    """Euristica simpla: cauta in acelasi bin alt clip cu aceeasi
    rezolutie si acelasi codec (din proprietatile Resolve), care NU e
    cel corupt. Nu e infailibil — recomand mereu sa lasi utilizatorul
    sa confirme fisierul de referinta ales."""
    corrupt_path = media_pool_item.GetClipProperty("File Path")
    corrupt_res = media_pool_item.GetClipProperty("Resolution")
    corrupt_codec = media_pool_item.GetClipProperty("Video Codec")

    for candidate in all_clips:
        cpath = candidate.GetClipProperty("File Path")
        if cpath == corrupt_path or not _is_video_file(cpath or ""):
            continue
        if (candidate.GetClipProperty("Resolution") == corrupt_res and
                candidate.GetClipProperty("Video Codec") == corrupt_codec):
            return cpath
    return None


def repair_clip(corrupt_path: str, reference_path: str, output_dir: str) -> tuple[bool, str, str]:
    """Ruleaza GDC Video Repair prin CLI. Intoarce (success, message, output_path)."""
    base = os.path.splitext(os.path.basename(corrupt_path))[0]
    output_path = os.path.join(output_dir, f"{base}_reparat.mp4")

    cmd = [
        GDC_REPAIR_CLI, GDC_REPAIR_SCRIPT,
        "--corrupt", corrupt_path,
        "--reference", reference_path,
        "--output", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.isfile(output_path):
        return True, result.stdout.strip() or "Reparat cu succes.", output_path
    return False, result.stderr.strip() or "Reparatia a esuat, fara mesaj de eroare de la CLI.", ""


def main():
    resolve = get_resolve()
    project_manager = resolve.GetProjectManager()
    project = project_manager.GetCurrentProject()
    if project is None:
        print("Nu exista niciun proiect deschis in Resolve.")
        return

    media_pool = project.GetMediaPool()
    current_folder = media_pool.GetCurrentFolder()
    all_clips = current_folder.GetClipList()

    targets = get_selected_clips(media_pool)
    if not targets:
        print("Nu am gasit clipuri video in folderul curent din Media Pool. "
              "Selecteaza folderul care contine clipul corupt si ruleaza din nou.")
        return

    output_dir = tempfile.mkdtemp(prefix="gdc_resolve_repair_")
    repaired_paths = []

    for clip in targets:
        corrupt_path = clip.GetClipProperty("File Path")
        print(f"Verific: {corrupt_path}")

        reference_path = _find_reference_candidate(clip, all_clips)
        if reference_path is None:
            print(f"  -> Nu am gasit automat un fisier de referinta potrivit pentru {corrupt_path}. Se sare peste.")
            continue

        print(f"  -> Fisier de referinta ales automat: {reference_path}")
        success, message, output_path = repair_clip(corrupt_path, reference_path, output_dir)

        if success:
            print(f"  -> Reparat: {message}")
            repaired_paths.append(output_path)
        else:
            print(f"  -> Esuat: {message}")

    if repaired_paths:
        imported = media_pool.ImportMedia(repaired_paths)
        print(f"\nImportate in Media Pool: {len(imported)} clip(uri) reparat(e), "
              f"in folderul '{current_folder.GetName()}'.")
    else:
        print("\nNiciun clip nu a fost reparat cu succes.")


if __name__ == "__main__":
    main()
