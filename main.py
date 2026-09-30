"""Simple graphical interface for comparing two folders."""

from __future__ import annotations

import csv
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import cast

from folder_compare import Difference, compare_folders


class FolderCompareApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Folder Compare")
        self.root.geometry("900x560")
        self.first_folder = tk.StringVar()
        self.second_folder = tk.StringVar()
        self.status = tk.StringVar(value="Choose two folders to compare.")
        self.results: list[Difference] = []
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        self._folder_row(frame, 0, "Folder 1:", self.first_folder)
        self._folder_row(frame, 1, "Folder 2:", self.second_folder)

        ttk.Label(
            frame,
            text=(
                "Checks folder structure, names, file contents, modified times, "
                "permissions, and symbolic-link targets."
            ),
            wraplength=850,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 6))
        ttk.Label(
            frame,
            text="File contents are read to compare them. OneDrive online-only files may download.",
            wraplength=850,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 8))

        columns = ("status", "path", "details")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        self.tree.heading("status", text="Difference")
        self.tree.heading("path", text="Path")
        self.tree.heading("details", text="Details")
        self.tree.column("status", width=180, anchor="w")
        self.tree.column("path", width=250, anchor="w")
        self.tree.column("details", width=420, anchor="w")
        self.tree.grid(row=4, column=0, columnspan=3, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=4, column=3, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.compare_button = ttk.Button(
            buttons, text="Compare folders", command=self.compare
        )
        self.compare_button.pack(side="left")
        self.export_button = ttk.Button(
            buttons,
            text="Save report as CSV",
            command=self.export_report,
            state="disabled",
        )
        self.export_button.pack(side="left", padx=(8, 0))
        ttk.Label(buttons, textvariable=self.status).pack(
            side="left", padx=(12, 0), fill="x", expand=True
        )

    def _folder_row(
        self, frame: ttk.Frame, row: int, label: str, variable: tk.StringVar
    ) -> None:
        ttk.Label(frame, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=3
        )
        ttk.Entry(frame, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=3
        )
        ttk.Button(
            frame, text="Browse...", command=lambda: self._browse(variable)
        ).grid(row=row, column=2, padx=(8, 0), pady=3)

    @staticmethod
    def _browse(variable: tk.StringVar) -> None:
        folder = filedialog.askdirectory(title="Choose a folder")
        if folder:
            variable.set(folder)

    def compare(self) -> None:
        first = self.first_folder.get().strip()
        second = self.second_folder.get().strip()
        if not first or not second:
            messagebox.showerror(
                "Choose folders", "Select both folders before comparing."
            )
            return
        if Path(first).resolve() == Path(second).resolve():
            messagebox.showerror(
                "Choose different folders", "The two folders are the same."
            )
            return

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results = []
        self.export_button.configure(state="disabled")
        self.compare_button.configure(state="disabled")
        self.status.set("Comparing files...")
        threading.Thread(
            target=self._compare_in_background, args=(first, second), daemon=True
        ).start()
        self.root.after(100, self._poll_events)

    def _compare_in_background(self, first: str, second: str) -> None:
        try:
            differences, matching_files = compare_folders(first, second)
            self.events.put(("success", (differences, matching_files)))
        except (OSError, ValueError) as error:
            self.events.put(("error", error))

    def _poll_events(self) -> None:
        try:
            event, value = self.events.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_events)
            return

        self.compare_button.configure(state="normal")
        if event == "error":
            self.status.set("Comparison failed.")
            messagebox.showerror("Could not compare folders", str(value))
            return

        differences, matching_files = cast(tuple[list[Difference], int], value)
        self.results = differences
        for difference in differences:
            self.tree.insert(
                "",
                "end",
                values=(difference.status, difference.path, difference.details),
            )
        if differences:
            self.status.set(
                f"Found {len(differences)} difference(s); {matching_files} file(s) have identical contents."
            )
            self.export_button.configure(state="normal")
        else:
            self.status.set(
                f"No differences found; {matching_files} file(s) have identical contents."
            )

    def export_report(self) -> None:
        destination = filedialog.asksaveasfilename(
            title="Save comparison report",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="folder-comparison.csv",
        )
        if not destination:
            return
        try:
            with open(destination, "w", newline="", encoding="utf-8-sig") as report:
                writer = csv.writer(report)
                writer.writerow(("Difference", "Path", "Details"))
                writer.writerows(
                    (difference.status, difference.path, difference.details)
                    for difference in self.results
                )
        except OSError as error:
            messagebox.showerror("Could not save report", str(error))
            return
        self.status.set(f"Report saved: {destination}")


def main() -> None:
    root = tk.Tk()
    FolderCompareApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
