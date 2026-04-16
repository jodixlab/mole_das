from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _app_root() -> Path:
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent.parent
    except Exception:
        pass
    return Path(__file__).resolve().parent.parent


def _default_registry_path() -> Path:
    return _app_root() / "config" / "mole_ui_help_registry_v1.json"


def load_ui_help_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    use_path = Path(path) if path is not None else _default_registry_path()
    try:
        payload = json.loads(use_path.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": {}}
    if not isinstance(payload, dict):
        return {"entries": {}}
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        payload["entries"] = {}
    return payload


def _doc_ref_lines(entry: Dict[str, Any]) -> List[str]:
    refs = entry.get("doc_refs") or []
    if not isinstance(refs, list):
        return []
    lines: List[str] = []
    for ref in refs[:4]:
        if not isinstance(ref, dict):
            continue
        doc_label = str(ref.get("doc_label") or ref.get("doc") or "").strip()
        section = str(ref.get("section") or "").strip()
        if doc_label and section:
            lines.append(f"- {doc_label} | {section}")
        elif doc_label:
            lines.append(f"- {doc_label}")
    return lines


def format_ui_help_tooltip(entry: Dict[str, Any]) -> str:
    lines: List[str] = []
    label = str(entry.get("label") or "").strip()
    if label:
        lines.append(label)
    short_desc = str(entry.get("short_description") or "").strip()
    if short_desc:
        if lines:
            lines.append("")
        lines.append(short_desc)
    definition = str(entry.get("definition") or "").strip()
    if definition:
        lines.append("")
        lines.append(f"Definition: {definition}")
    process = str(entry.get("process_note") or "").strip()
    if process:
        lines.append("")
        lines.append(f"Process: {process}")
    refs = _doc_ref_lines(entry)
    if refs:
        lines.append("")
        lines.append("Docs:")
        lines.extend(refs)
    return "\n".join(lines).strip()


class UIHelpTooltipManager:
    def __init__(self, root: Any, registry_payload: Dict[str, Any]):
        self.root = root
        self.registry = (registry_payload or {}).get("entries") or {}
        self._tip_window = None
        self._after_id = None
        self._active_widget = None

    def bind(self, widget: Any, help_id: str) -> None:
        entry = self.registry.get(help_id)
        if not isinstance(entry, dict):
            return
        widget.bind("<Enter>", lambda _e: self._schedule(widget, entry), add="+")
        widget.bind("<Leave>", lambda _e: self.hide(), add="+")
        widget.bind("<ButtonPress>", lambda _e: self.hide(), add="+")
        widget.bind("<FocusOut>", lambda _e: self.hide(), add="+")

    def _schedule(self, widget: Any, entry: Dict[str, Any]) -> None:
        self.hide()
        self._active_widget = widget
        self._after_id = self.root.after(450, lambda: self._show(widget, entry))

    def _show(self, widget: Any, entry: Dict[str, Any]) -> None:
        self.hide()
        text = format_ui_help_tooltip(entry)
        if not text:
            return
        try:
            x = widget.winfo_rootx() + 18
            y = widget.winfo_rooty() + widget.winfo_height() + 10
        except Exception:
            return
        import tkinter as tk

        tip = self._tip_window = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        try:
            tip.attributes("-topmost", True)
        except Exception:
            pass

        frame = tk.Frame(tip, bg="#111827", bd=1, relief="solid")
        frame.pack(fill="both", expand=True)
        lbl = tk.Label(
            frame,
            text=text,
            justify="left",
            anchor="w",
            bg="#111827",
            fg="#F3F4F6",
            wraplength=460,
            padx=10,
            pady=8,
            font=("Consolas", 9),
        )
        lbl.pack(fill="both", expand=True)

    def hide(self) -> None:
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None
        self._active_widget = None


def get_ui_help_tooltip_manager(root: Any) -> UIHelpTooltipManager:
    mgr = getattr(root, "_mole_ui_help_tooltip_manager", None)
    if mgr is not None:
        return mgr
    payload = load_ui_help_registry()
    mgr = UIHelpTooltipManager(root, payload)
    setattr(root, "_mole_ui_help_tooltip_manager", mgr)
    return mgr
