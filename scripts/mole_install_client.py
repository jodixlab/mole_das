from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _default_install_root() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return (Path(local) / "Programs" / "MOLE_DAS").resolve()


def _resolve_package_root(arg_value: str | None) -> Path:
    if arg_value:
        return Path(arg_value).expanduser().resolve()
    here = Path(__file__).resolve().parent
    if (here / "runtime").exists():
        return here
    if (here.parent / "runtime").exists():
        return here.parent.resolve()
    return here


def _package_summary(package_root: Path) -> Dict[str, Any]:
    runtime_root = package_root / "runtime"
    build_identity_path = runtime_root / "config" / "mole_build_identity_v1.json"
    verified_release_path = package_root / "latest_verified_release_v1.json"
    acceptance_json_path = package_root / "PACKAGED_ACCEPTANCE_SUMMARY.json"
    version_audit_path = package_root / "PACKAGE_VERSION_AUDIT.json"
    immutable_audit_path = package_root / "IMMUTABLE_PACKAGE_AUDIT.json"
    installer_script_path = package_root / "INSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
    uninstall_script_path = package_root / "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
    launcher_path = package_root / "LAUNCH_MOLE_DAS_EXE.bat"
    build_identity = _load_json(build_identity_path)
    verified_release = _load_json(verified_release_path)
    acceptance = _load_json(acceptance_json_path)
    version_audit = _load_json(version_audit_path)
    immutable_audit = _load_json(immutable_audit_path)
    return {
        "package_root": str(package_root),
        "runtime_root": str(runtime_root),
        "build_identity_path": str(build_identity_path),
        "verified_release_path": str(verified_release_path),
        "acceptance_json_path": str(acceptance_json_path),
        "version_audit_path": str(version_audit_path),
        "immutable_audit_path": str(immutable_audit_path),
        "installer_script_path": str(installer_script_path),
        "uninstall_script_path": str(uninstall_script_path),
        "launcher_path": str(launcher_path),
        "package_label": str(build_identity.get("bundle_label") or verified_release.get("package_label") or package_root.name),
        "git_commit": str(build_identity.get("git_commit") or verified_release.get("git_commit") or ""),
        "git_branch": str(build_identity.get("git_branch") or verified_release.get("git_branch") or ""),
        "acceptance_status": str(acceptance.get("status") or verified_release.get("acceptance_status") or ""),
        "version_audit_status": str(version_audit.get("status") or ""),
        "immutable_audit_status": str(immutable_audit.get("status") or ""),
        "verified_release_channel": str(verified_release.get("channel_name") or ""),
        "build_identity": build_identity,
        "verified_release": verified_release,
        "acceptance": acceptance,
        "version_audit": version_audit,
        "immutable_audit": immutable_audit,
        "has_data_payload": (package_root / "data").exists() and any((package_root / "data").rglob("*")),
    }


def _installed_summary(install_root: Path) -> Dict[str, Any]:
    install_manifest_path = install_root / "mole_install_manifest_v1.json"
    build_identity_path = install_root / "runtime" / "config" / "mole_build_identity_v1.json"
    data_root_manifest_path = install_root / "data" / "data_root_manifest_v1.json"
    wizard_exe = install_root / "runtime" / "MOLE_code" / "MOLE_DAS_Wizard.exe"
    uninstall_script = install_root / "UNINSTALL_MOLE_DAS_EXE_BUNDLE.ps1"
    install_manifest = _load_json(install_manifest_path)
    build_identity = _load_json(build_identity_path)
    data_manifest = _load_json(data_root_manifest_path)
    return {
        "install_root": str(install_root),
        "exists": install_root.exists(),
        "install_manifest_path": str(install_manifest_path),
        "build_identity_path": str(build_identity_path),
        "data_root_manifest_path": str(data_root_manifest_path),
        "wizard_exe_path": str(wizard_exe),
        "uninstall_script_path": str(uninstall_script),
        "bundle_label": str(build_identity.get("bundle_label") or install_manifest.get("bundle_label") or ""),
        "installed_at": str(install_manifest.get("installed_at") or ""),
        "data_schema_version": str(data_manifest.get("data_schema_version") or ""),
        "data_manifest_present": data_root_manifest_path.exists(),
    }


def _open_path(path_value: str) -> None:
    path = Path(path_value)
    if not path.exists():
        messagebox.showwarning("Open Path", f"Path not found:\n{path}")
        return
    os.startfile(str(path))


def _run_powershell(script_path: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *args,
    ]
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)


class InstallClient(tk.Tk):
    def __init__(self, package_root: Path) -> None:
        super().__init__()
        self.package_root = package_root
        self.package = _package_summary(package_root)
        self.title("MOLE-DAS Installation Client")
        self.geometry("1040x760")
        self.configure(bg="#0b1118")
        try:
            icon = package_root / "MOLE_DAS.ico"
            if icon.exists():
                self.iconbitmap(default=str(icon))
        except Exception:
            pass

        self.install_root_var = tk.StringVar(value=str(_default_install_root()))
        self.launch_after_install_var = tk.BooleanVar(value=True)
        self.desktop_shortcut_var = tk.BooleanVar(value=True)
        self.start_menu_var = tk.BooleanVar(value=True)
        self.uninstall_reg_var = tk.BooleanVar(value=True)
        self.current_install = _installed_summary(Path(self.install_root_var.get()))

        self._build_ui()
        self._refresh_state()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text="MOLE-DAS Installation Client", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w")
        subtitle = ttk.Label(
            outer,
            text="1. Verify package. 2. Choose install root. 3. Install, upgrade, repair, or uninstall.",
        )
        subtitle.pack(anchor="w", pady=(0, 12))

        top = ttk.Frame(outer)
        top.pack(fill="x")

        package_box = ttk.LabelFrame(top, text="Package Verification", padding=12)
        package_box.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.package_text = tk.Text(package_box, height=11, width=60, wrap="word")
        self.package_text.pack(fill="both", expand=True)

        install_box = ttk.LabelFrame(top, text="Install Target", padding=12)
        install_box.pack(side="left", fill="both", expand=True)
        entry_row = ttk.Frame(install_box)
        entry_row.pack(fill="x")
        ttk.Entry(entry_row, textvariable=self.install_root_var).pack(side="left", fill="x", expand=True)
        ttk.Button(entry_row, text="Browse", command=self._browse_install_root).pack(side="left", padx=(8, 0))
        self.install_text = tk.Text(install_box, height=11, width=48, wrap="word")
        self.install_text.pack(fill="both", expand=True, pady=(8, 0))

        options = ttk.LabelFrame(outer, text="Options", padding=12)
        options.pack(fill="x", pady=(12, 0))
        ttk.Checkbutton(options, text="Launch Wizard after install", variable=self.launch_after_install_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Create Desktop shortcut", variable=self.desktop_shortcut_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Create Start Menu shortcuts", variable=self.start_menu_var).pack(anchor="w")
        ttk.Checkbutton(options, text="Register uninstall entry", variable=self.uninstall_reg_var).pack(anchor="w")

        actions = ttk.LabelFrame(outer, text="Actions", padding=12)
        actions.pack(fill="x", pady=(12, 0))
        row1 = ttk.Frame(actions)
        row1.pack(fill="x")
        ttk.Button(row1, text="Refresh", command=self._refresh_state).pack(side="left")
        ttk.Button(row1, text="Validate Package", command=self._validate_package).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Install / Upgrade", command=self._install_package).pack(side="left", padx=(8, 0))
        ttk.Button(row1, text="Repair Install", command=self._repair_install).pack(side="left", padx=(8, 0))
        row2 = ttk.Frame(actions)
        row2.pack(fill="x", pady=(8, 0))
        ttk.Button(row2, text="Uninstall Installed Copy", command=self._uninstall_install).pack(side="left")
        ttk.Button(row2, text="Launch Installed App", command=self._launch_installed).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="Open Install Root", command=lambda: _open_path(self.install_root_var.get())).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="Open Acceptance Summary", command=lambda: _open_path(self.package["acceptance_json_path"])).pack(side="left", padx=(8, 0))
        ttk.Button(row2, text="Open Verified Release", command=lambda: _open_path(self.package["verified_release_path"])).pack(side="left", padx=(8, 0))

        log_box = ttk.LabelFrame(outer, text="Install Log", padding=12)
        log_box.pack(fill="both", expand=True, pady=(12, 0))
        self.log = tk.Text(log_box, wrap="word")
        self.log.pack(fill="both", expand=True)

    def _browse_install_root(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.install_root_var.get() or str(Path.home()))
        if selected:
            self.install_root_var.set(str(Path(selected).resolve()))
            self._refresh_state()

    def _write_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _append_log(self, content: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", content.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_state(self) -> None:
        self.package = _package_summary(self.package_root)
        self.current_install = _installed_summary(Path(self.install_root_var.get()))
        package_lines = [
            f"Package label: {self.package['package_label']}",
            f"Git commit: {self.package['git_commit']}",
            f"Git branch: {self.package['git_branch']}",
            f"Acceptance: {self.package['acceptance_status'] or '(missing)'}",
            f"Version audit: {self.package['version_audit_status'] or '(missing)'}",
            f"Immutable audit: {self.package['immutable_audit_status'] or '(missing)'}",
            f"Verified channel: {self.package['verified_release_channel'] or '(none)'}",
            f"Package root: {self.package['package_root']}",
            f"Runtime root: {self.package['runtime_root']}",
            f"Portable data payload present: {'yes' if self.package['has_data_payload'] else 'no'}",
        ]
        install_lines = [
            f"Install root: {self.current_install['install_root']}",
            f"Installed: {'yes' if self.current_install['exists'] else 'no'}",
            f"Installed label: {self.current_install['bundle_label'] or '(none)'}",
            f"Installed at: {self.current_install['installed_at'] or '(unknown)'}",
            f"Data manifest present: {'yes' if self.current_install['data_manifest_present'] else 'no'}",
            f"Data schema version: {self.current_install['data_schema_version'] or '(none)'}",
            f"Wizard path: {self.current_install['wizard_exe_path']}",
        ]
        self._write_text(self.package_text, "\n".join(package_lines))
        self._write_text(self.install_text, "\n".join(install_lines))

    def _validate_package(self) -> None:
        failures = []
        if self.package["acceptance_status"] != "PASS":
            failures.append("Packaged acceptance is not PASS.")
        if self.package["version_audit_status"] != "PASS":
            failures.append("Package version audit is not PASS.")
        if self.package["immutable_audit_status"] != "PASS":
            failures.append("Immutable package audit is not PASS.")
        if not Path(self.package["installer_script_path"]).exists():
            failures.append("Installer script is missing.")
        if failures:
            messagebox.showerror("Validate Package", "\n".join(failures))
            self._append_log("Package validation failed:\n" + "\n".join(failures))
            return
        self._append_log(f"Package validation passed for {self.package['package_label']}.")
        messagebox.showinfo("Validate Package", "Package validation passed.")

    def _install_args(self) -> list[str]:
        args = ["-InstallRoot", self.install_root_var.get()]
        if not self.launch_after_install_var.get():
            args.append("-NoLaunch")
        if not self.desktop_shortcut_var.get():
            args.append("-NoDesktopShortcut")
        if not self.start_menu_var.get():
            args.append("-NoStartMenuShortcut")
        if not self.uninstall_reg_var.get():
            args.append("-NoUninstallRegistration")
        return args

    def _run_async(self, label: str, script_path: Path, args: list[str]) -> None:
        def worker() -> None:
            self._append_log(f"{label} started.")
            result = _run_powershell(script_path, args, self.package_root)
            if result.stdout:
                self._append_log(result.stdout)
            if result.stderr:
                self._append_log(result.stderr)
            if result.returncode == 0:
                self._append_log(f"{label} completed successfully.")
                self.after(0, self._refresh_state)
                self.after(0, lambda: messagebox.showinfo(label, f"{label} completed successfully."))
            else:
                self._append_log(f"{label} failed with exit code {result.returncode}.")
                self.after(0, lambda: messagebox.showerror(label, f"{label} failed.\n\nExit code: {result.returncode}"))

        threading.Thread(target=worker, daemon=True).start()

    def _install_package(self) -> None:
        self._run_async("Install / Upgrade", Path(self.package["installer_script_path"]), self._install_args())

    def _repair_install(self) -> None:
        self._run_async("Repair Install", Path(self.package["installer_script_path"]), self._install_args())

    def _uninstall_install(self) -> None:
        uninstall_script = Path(self.current_install["uninstall_script_path"])
        if not uninstall_script.exists():
            messagebox.showwarning("Uninstall", f"Uninstall script not found:\n{uninstall_script}")
            return
        self._run_async("Uninstall", uninstall_script, ["-InstallRoot", self.install_root_var.get()])

    def _launch_installed(self) -> None:
        wizard = Path(self.current_install["wizard_exe_path"])
        if not wizard.exists():
            messagebox.showwarning("Launch Installed App", f"Installed Wizard not found:\n{wizard}")
            return
        subprocess.Popen([str(wizard)], cwd=str(wizard.parent))
        self._append_log(f"Launched installed Wizard: {wizard}")


def main() -> int:
    parser = argparse.ArgumentParser(description="MOLE-DAS installation client")
    parser.add_argument("--package-root", default="", help="Override package root")
    parser.add_argument("--headless-summary", action="store_true", help="Print package/install summary JSON and exit")
    args = parser.parse_args()

    package_root = _resolve_package_root(args.package_root or None)
    package = _package_summary(package_root)
    installed = _installed_summary(_default_install_root())
    if args.headless_summary:
        print(
            json.dumps(
                {
                    "schema": "mole_install_client_summary_v1",
                    "package": package,
                    "installed": installed,
                },
                indent=2,
            )
        )
        return 0

    app = InstallClient(package_root)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
