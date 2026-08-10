#!/usr/bin/env python3
"""
GDC Video Repair — interfata grafica (Tkinter).
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import repair_engine


class GdcVideoRepairApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GDC Video Repair")
        self.geometry("620x420")
        self.minsize(560, 380)

        self.corrupt_path = tk.StringVar()
        self.reference_path = tk.StringVar()
        self.output_path = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="GDC Video Repair", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(body, text="Repara fisiere video corupte folosind un fisier de referinta sanatos.",
                  foreground="#666").pack(anchor="w", pady=(0, 16))

        self._file_row(body, "Fisier corupt:", self.corrupt_path, self._browse_corrupt)
        self._file_row(body, "Fisier de referinta (sanatos):", self.reference_path, self._browse_reference)
        self._file_row(body, "Salveaza reparat ca:", self.output_path, self._browse_output, save=True)

        ttk.Label(body, text="Fisierul de referinta trebuie filmat cu aceeasi camera si "
                              "aceleasi setari (rezolutie, codec, framerate) ca fisierul corupt.",
                  foreground="#888", font=("", 9), wraplength=560, justify="left").pack(anchor="w", pady=(4, 16))

        self.repair_btn = ttk.Button(body, text="Repara", command=self._start_repair)
        self.repair_btn.pack(anchor="w", pady=(0, 12))

        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))

        self.status_var = tk.StringVar(value="")
        ttk.Label(body, textvariable=self.status_var, foreground="#444", wraplength=560,
                  justify="left").pack(anchor="w", fill="x")

    def _file_row(self, parent, label, var, browse_cmd, save=False):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=28).pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="Alege...", command=browse_cmd).pack(side="left")

    def _browse_corrupt(self):
        path = filedialog.askopenfilename(title="Alege fisierul corupt",
                                           filetypes=[("Video", "*.mp4 *.mov *.m4v"), ("Toate fisierele", "*.*")])
        if path:
            self.corrupt_path.set(path)
            if not self.output_path.get():
                base, ext = os.path.splitext(path)
                self.output_path.set(f"{base}_reparat{ext}")

    def _browse_reference(self):
        path = filedialog.askopenfilename(title="Alege fisierul de referinta (sanatos)",
                                           filetypes=[("Video", "*.mp4 *.mov *.m4v"), ("Toate fisierele", "*.*")])
        if path:
            self.reference_path.set(path)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(title="Salveaza fisierul reparat ca",
                                             defaultextension=".mp4",
                                             filetypes=[("MP4", "*.mp4"), ("MOV", "*.mov")])
        if path:
            self.output_path.set(path)

    def _start_repair(self):
        corrupt = self.corrupt_path.get().strip()
        reference = self.reference_path.get().strip()
        output = self.output_path.get().strip()

        if not corrupt or not os.path.isfile(corrupt):
            messagebox.showwarning("Fisier lipsa", "Alege un fisier corupt valid.")
            return
        if not output:
            messagebox.showwarning("Destinatie lipsa", "Alege unde sa fie salvat fisierul reparat.")
            return

        self.repair_btn.config(state="disabled")
        self.progress.start(12)
        self.status_var.set("Pornesc...")

        thread = threading.Thread(target=self._run_repair, args=(corrupt, reference, output), daemon=True)
        thread.start()

    def _run_repair(self, corrupt, reference, output):
        def report(msg):
            self.after(0, self.status_var.set, msg)

        result = repair_engine.repair(corrupt, reference or None, output, progress_callback=report)
        self.after(0, self._on_repair_done, result)

    def _on_repair_done(self, result):
        self.progress.stop()
        self.repair_btn.config(state="normal")
        self.status_var.set(result.message)
        if result.success:
            messagebox.showinfo("Reparat cu succes", f"{result.message}\n\nSalvat la:\n{result.output_path}")
        else:
            messagebox.showerror("Reparare esuata", result.message)


if __name__ == "__main__":
    app = GdcVideoRepairApp()
    app.mainloop()
