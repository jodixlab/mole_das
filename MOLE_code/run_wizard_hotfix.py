"""
MOLE-DAS Wizard Hotfix Launcher (Runtime Repair)
------------------------------------------------
This launcher loads the main MOLE-DAS wizard module and applies a few
runtime patches so the program can run from a clean install package.

Patches included:
1) Method rebind ("detached methods" fix)
   - Some builds can contain wizard methods compiled as nested functions
     inside _build_intake() (or other builders) instead of as class methods.
   - We recover those code objects and bind them back onto MoleDASWizard
     before the UI is constructed (prevents startup crashes like:
       AttributeError: ... has no attribute 'load_existing').

2) Save + Apply behavior
   - Adds an operator escape hatch when ONLY the Job Intake checklist is
     blocking SIM/TEST flows (optional non-compliance save).

3) Non-blocking coordinate fetch
   - Runs coordinate cascade in a background thread and applies results
     on the Tk thread (prevents UI hang).
"""

from __future__ import annotations

import importlib.util
import inspect
import queue
import threading
import types
from pathlib import Path


HERE = Path(__file__).resolve().parent

# Prefer the canonical build, but fall back to newest matching file if needed.
WIZ = HERE / "mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py"
if not WIZ.exists():
    candidates = sorted(HERE.glob("mole_code_das_*_ARCADE_RELEASE.py"))
    if candidates:
        WIZ = candidates[-1]


def _load_wizard_module(path: Path):
    spec = importlib.util.spec_from_file_location("mole_wizard", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load wizard module spec: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bind_detached_methods(mod, cls) -> list[str]:
    """
    Bind functions that look like class methods back onto MoleDASWizard.

    Strategy:
      A) Any module-level function that takes (self, ...) is treated as a
         detached method candidate.
      B) For every function in the module, scan nested code objects for
         defs that take (self, ...) and bind them too.
    """
    patched: list[str] = []

    # A) Module-level detached methods
    for name, obj in list(mod.__dict__.items()):
        if inspect.isfunction(obj):
            try:
                if obj.__code__.co_argcount >= 1 and obj.__code__.co_varnames[0] == "self":
                    if not hasattr(cls, name):
                        setattr(cls, name, obj)
                        patched.append(name)
            except Exception:
                # keep going; best-effort
                continue

    # B) Nested defs inside module functions (common indentation/packaging failure mode)
    for _, outer in list(mod.__dict__.items()):
        if not inspect.isfunction(outer):
            continue
        try:
            consts = outer.__code__.co_consts
        except Exception:
            continue

        for c in consts:
            if not isinstance(c, types.CodeType):
                continue
            if not c.co_name or c.co_name == "<lambda>":
                continue
            try:
                if c.co_argcount >= 1 and c.co_varnames and c.co_varnames[0] == "self":
                    if not hasattr(cls, c.co_name):
                        fn = types.FunctionType(c, mod.__dict__)
                        setattr(cls, c.co_name, fn)
                        patched.append(c.co_name)
            except Exception:
                continue

    # Dedupe while preserving order
    seen = set()
    out: list[str] = []
    for n in patched:
        if n not in seen:
            out.append(n)
            seen.add(n)
    return out


# -------------------------------
# Load + patch module
# -------------------------------

m = _load_wizard_module(WIZ)

MoleDASWizard = getattr(m, "MoleDASWizard", None)
if MoleDASWizard is None:
    raise RuntimeError("MoleDASWizard class not found in wizard module.")

# Fix startup crashes by rebinding detached methods BEFORE instantiation.
patched_names = _bind_detached_methods(m, MoleDASWizard)
try:
    print(f"[MOLE-DAS] Hotfix: rebound {len(patched_names)} detached method(s).")
except Exception:
    pass


# -------------------------------
# Patch: Test Matrix Acquisition Plan auto-save
# -------------------------------

def _tm_commit_plan_from_vars(self) -> None:
    """Commit Acquisition Plan (sample runs / minutes) from Test Matrix UI vars into session.

    Upstream behavior: these plan fields are only persisted when the operator clicks
    the "Save Test Matrix" button. If the operator edits the Acquisition Plan and then
    navigates away or uses "Save + Apply Config" without clicking "Save Test Matrix",
    changes can appear to not save.

    This hotfix auto-commits the plan whenever we navigate or Save+Apply.
    """
    try:
        if not hasattr(self, "var_tm_sample_runs") or not hasattr(self, "var_tm_minutes_per_run"):
            return
        sr_raw = (self.var_tm_sample_runs.get() or "").strip()
        mr_raw = (self.var_tm_minutes_per_run.get() or "").strip()
        if not sr_raw and not mr_raw:
            return
    except Exception:
        return

    # Parse values (sr is int; mr supports float minutes)
    try:
        sr = int(float(sr_raw))
    except Exception:
        return
    sr = max(1, min(999, sr))

    try:
        mr = float(mr_raw)
    except Exception:
        mr = 10.0
    if mr <= 0:
        mr = 10.0

    try:
        tm = self.session.get("test_matrix")
        if not isinstance(tm, dict):
            tm = {}
            self.session["test_matrix"] = tm

        plan = tm.get("plan")
        if not isinstance(plan, dict):
            plan = {}
            tm["plan"] = plan

        plan["sample_runs"] = sr
        plan["minutes_per_run"] = mr

        # Default + per-channel log intervals (best-effort)
        if hasattr(self, "var_tm_default_log_interval_s"):
            try:
                dli = int(float((self.var_tm_default_log_interval_s.get() or "60").strip()))
                plan["default_log_interval_s"] = max(1, dli)
            except Exception:
                pass

        if hasattr(self, "_tm_channel_interval_vars"):
            try:
                ch = plan.get("channel_log_interval_s")
                if not isinstance(ch, dict):
                    ch = {}
                for a, v in (getattr(self, "_tm_channel_interval_vars", {}) or {}).items():
                    try:
                        val = int(float((v.get() or "").strip()))
                    except Exception:
                        val = int(plan.get("default_log_interval_s") or 60)
                    ch[str(a)] = max(1, val)
                plan["channel_log_interval_s"] = ch
            except Exception:
                pass

        # Per-run duration overrides (minutes)
        rd = []
        vars_list = getattr(self, "_tm_run_duration_vars", None)
        if isinstance(vars_list, list):
            for i in range(sr):
                try:
                    if i < len(vars_list):
                        s = (vars_list[i].get() or "").strip()
                        rd.append(float(s) if s else mr)
                    else:
                        rd.append(mr)
                except Exception:
                    rd.append(mr)
        else:
            rd = [mr] * sr
        plan["run_durations_min"] = rd

        tm["plan"] = plan
        self.session["test_matrix"] = tm

        # Keep the RUNS step summary in-sync (if present)
        try:
            steps = tm.get("steps_existing")
            if isinstance(steps, list):
                for st in steps:
                    if (st.get("step_id") or "").upper() == "RUNS":
                        st["notes"] = f"Sampling runs: {sr} run(s) × {mr:g} minute(s) per run"
        except Exception:
            pass

    except Exception:
        # Never block navigation/save due to plan parsing.
        return


# -------------------------------
# Patch: Save + Apply behavior
# -------------------------------

def _patched_save_and_apply(self) -> None:
    """Save config and enable nav.

    If the only blocker is the Job Intake checklist (when compliance may be supported),
    offer an operator escape hatch to save in non-compliance mode so SIM/TEST can proceed.
    """
    mb = getattr(m, "messagebox", None)

    # Keep original behavior where possible
    try:
        self._sync_session_from_vars()
    except Exception:
        pass

    # Hotfix: capture Acquisition Plan edits (Test Matrix) even if operator did not click 'Save Test Matrix'
    try:
        _tm_commit_plan_from_vars(self)
    except Exception:
        pass

    # Ensure deterministic binding before validation (same as upstream intent)
    try:
        self._pollutants_resolve_and_bind()
    except Exception:
        pass

    try:
        self._ensure_test_matrix()
    except Exception:
        pass

    # Validate
    try:
        err = self._validate_before_apply()
    except Exception as e:
        err = str(e)

    if err:
        s = str(err)

        # Special-case: intake checklist gate should not brick SIM/TEST workflows.
        if s.startswith("Job Intake Checklist incomplete"):
            proceed = False
            if mb:
                try:
                    proceed = mb.askyesno(
                        "Job Intake Incomplete",
                        "Job Intake Checklist is incomplete.\n\n"
                        "To proceed with Simulation/Testing setup, you can save the config in NON-COMPLIANCE mode.\n\n"
                        "YES = disable 'May Support Compliance' for this session and save anyway.\n"
                        "NO  = return and complete the intake checklist.",
                    )
                except Exception:
                    proceed = False

            if not proceed:
                if mb:
                    try:
                        mb.showerror("Save + Apply", err)
                    except Exception:
                        pass
                return

            # Disable compliance and retry validation
            try:
                self.var_may_support_compliance.set(False)
            except Exception:
                # fallback direct edit
                try:
                    sm = self.session.get("session_mode") or {}
                    sm["may_support_compliance"] = False
                    self.session["session_mode"] = sm
                except Exception:
                    pass

            try:
                self._sync_session_from_vars()
            except Exception:
                pass

            try:
                err2 = self._validate_before_apply()
            except Exception as e:
                err2 = str(e)

            if err2:
                if mb:
                    try:
                        mb.showerror("Save + Apply", err2)
                    except Exception:
                        pass
                return

        # Original AUTO_WEATHER UX: offer jump to Site Conditions
        elif s.startswith("AUTO_WEATHER"):
            if mb:
                try:
                    mb.showerror("Save + Apply", err)
                    try:
                        if mb.askyesno("Site Conditions", "Open Site Conditions now?"):
                            self.goto("SITE")
                    except Exception:
                        pass
                except Exception:
                    pass
            return

        else:
            if mb:
                try:
                    mb.showerror("Save + Apply", err)
                except Exception:
                    pass
            return

    # Write config (same as upstream intent)
    try:
        job = self.session["project"]["job_id"]
    except Exception:
        job = "UNKNOWN"

    out_path = getattr(self, "config_dir", HERE) / f"mole_session_{job}.json"

    try:
        self._catalog_learn_from_session()
    except Exception:
        pass

    try:
        self.session.setdefault("meta", {})["applied_iso"] = m.now_iso()
    except Exception:
        pass

    try:
        self.session.setdefault("paths", {})["session_config_path"] = str(out_path)
    except Exception:
        pass

    try:
        m.write_json(out_path, self.session)
    except Exception as e:
        if mb:
            try:
                mb.showerror("Save + Apply", f"Failed to write config:\n{out_path}\n\n{e}")
            except Exception:
                pass
        return

    try:
        self.nav_enabled = True
        self._refresh_nav()
    except Exception:
        pass

    if mb:
        try:
            mb.showinfo("Save + Apply", f"Config written:\n{out_path}")
        except Exception:
            pass


# Bind patch (overrides whatever was rebound)
MoleDASWizard.save_and_apply = _patched_save_and_apply


# -------------------------------
# Patch: Auto-commit Acquisition Plan on navigation
# -------------------------------

_orig_goto = getattr(MoleDASWizard, 'goto', None)

def _patched_goto(self, state: str) -> None:
    try:
        _tm_commit_plan_from_vars(self)
    except Exception:
        pass
    if _orig_goto is None:
        return
    return _orig_goto(self, state)

if _orig_goto is not None:
    MoleDASWizard.goto = _patched_goto


# -------------------------------
# Patch: Non-blocking coordinate fetch
# -------------------------------

def _patched_fetch_coordinates_button(self) -> None:
    """Run coordinate cascade in a background thread and apply results on the Tk thread."""
    mb = getattr(m, "messagebox", None)

    # Snapshot session vars on UI thread
    try:
        self._sync_session_from_vars()
    except Exception:
        pass

    try:
        self.var_site_last_coords.set("Coords: fetching...")
    except Exception:
        pass

    q: "queue.Queue[dict]" = queue.Queue()

    def worker() -> None:
        attempts = []
        methods = [
            ("GNSS", getattr(self, "_coords_try_gnss_nmea", None)),
            ("CELLULAR", getattr(self, "_coords_try_cellular_at", None)),
            ("WIFI", getattr(self, "_coords_try_wifi_mls", None)),
            ("IP", getattr(self, "_coords_try_ip_geolocation", None)),
        ]
        lat = lon = None
        src = ""
        meta = {}
        for name, fn in methods:
            if fn is None:
                continue
            try:
                attempts.append(name)
                res = fn()
                if res:
                    lat, lon, src, meta = res
                    break
            except Exception:
                continue
        q.put({"lat": lat, "lon": lon, "src": src, "meta": meta, "attempts": attempts})

    def poll() -> None:
        try:
            res = q.get_nowait()
        except queue.Empty:
            try:
                self.after(100, poll)
            except Exception:
                pass
            return

        lat = res.get("lat")
        lon = res.get("lon")
        src = res.get("src") or ""
        meta = res.get("meta") or {}
        attempts = res.get("attempts") or []

        if lat is None or lon is None:
            try:
                self.var_site_last_coords.set(f"Coords: (unresolved)  Tried: {', '.join(attempts)}")
            except Exception:
                pass
            if mb:
                try:
                    mb.showwarning(
                        "Fetch Coordinates",
                        "Unable to fetch coordinates automatically.\n\n"
                        "Tried: " + ", ".join(attempts) + "\n\n"
                        "Tips:\n"
                        "- If using GNSS, ensure a GNSS receiver is connected and outputting NMEA.\n"
                        "- If using WiFi/IP, confirm internet access.\n"
                        "- You can always enter Lat/Lon manually.",
                    )
                except Exception:
                    pass
            return

        # Apply to UI + session
        try:
            self.var_site_lat.set(f"{float(lat):.6f}")
            self.var_site_lon.set(f"{float(lon):.6f}")
        except Exception:
            pass

        # Elevation best-effort
        try:
            elev_ft = self._noaa_fetch_point_elevation_ft(float(lat), float(lon))
        except Exception:
            elev_ft = None

        try:
            if elev_ft is not None and not (self.var_site_elev_ft_msl.get() or "").strip():
                self.var_site_elev_ft_msl.set(f"{elev_ft:.1f}")
        except Exception:
            pass

        try:
            self.var_site_last_coords.set(f"Coords: {float(lat):.6f}, {float(lon):.6f}  (source: {src})")
        except Exception:
            pass

        try:
            sc = self.session.get("site_conditions") or {}
            loc = sc.get("location")
            if not isinstance(loc, dict):
                loc = {}
                sc["location"] = loc
            loc["lat"] = float(lat)
            loc["lon"] = float(lon)
            loc["datum"] = "WGS84"
            loc["source"] = src
            loc["timestamp_iso"] = m.now_iso()
            if meta:
                loc["meta"] = meta
            self.session["site_conditions"] = sc
        except Exception:
            pass

        try:
            self._refresh_nav()
        except Exception:
            pass

        if mb:
            try:
                mb.showinfo("Fetch Coordinates", f"Coordinates set from {src}:\n{float(lat):.6f}, {float(lon):.6f}")
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()
    try:
        self.after(50, poll)
    except Exception:
        poll()


MoleDASWizard._fetch_coordinates_button = _patched_fetch_coordinates_button


# -------------------------------
# Launch
# -------------------------------
if __name__ == "__main__":
    MoleDASWizard().mainloop()
