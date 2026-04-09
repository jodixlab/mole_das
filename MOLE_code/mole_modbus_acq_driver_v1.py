from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from mole_modbus_poll_v1 import poll_modbus_channel


def _now_iso() -> str:
    try:
        return datetime.now().astimezone().isoformat(timespec="seconds")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _runtime_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _runtime_config_path() -> Path:
    return _runtime_root() / "config" / "mole_config.json"


def _load_runtime_config() -> Dict[str, Any]:
    p = _runtime_config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _active_hardware_profile(cfg: Dict[str, Any]) -> Dict[str, Any]:
    hw = cfg.get("hardware") or {}
    profile_key = str(hw.get("profile_id") or "").strip()
    profiles = cfg.get("hardware_profiles") or []
    if not isinstance(profiles, list):
        return {}
    for prof in profiles:
        if str((prof or {}).get("profile_key") or "").strip() == profile_key:
            return prof if isinstance(prof, dict) else {}
    for prof in profiles:
        if isinstance(prof, dict):
            return prof
    return {}


def _merged_profile_channels(profile: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    defaults = profile.get("defaults") or {}
    for row in (profile.get("channels") or []):
        if not isinstance(row, dict):
            continue
        channel_id = str(row.get("channel_id") or "").strip()
        if not channel_id:
            continue
        merged = dict(defaults)
        merged.update(row)
        out[channel_id] = merged
    return out


def _comm_protocol_from_prescription(pres: Dict[str, Any], fallback: str = "") -> str:
    comm = pres.get("comm") if isinstance(pres.get("comm"), dict) else {}
    proto = str(comm.get("protocol") or "").strip().upper()
    if not proto or proto == "AUTO":
        proto = str(fallback or "").strip().upper()
    return proto


def _merge_comm_params(base: Dict[str, Any], pres: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    comm = pres.get("comm") if isinstance(pres.get("comm"), dict) else {}
    params = comm.get("params") if isinstance(comm.get("params"), dict) else {}
    for key in (
        "host",
        "port",
        "unit_id",
        "timeout_s",
        "serial_port",
        "baud",
        "parity",
        "stopbits",
    ):
        value = params.get(key)
        if value not in (None, "", "None"):
            merged[key] = value
    return merged


def _resolve_binding(
    code: str,
    pres: Dict[str, Any],
    channel_map: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    channel_id = str(pres.get("channel_id") or pres.get("instrument_channel") or code).strip()
    channel = dict(channel_map.get(channel_id) or {})
    proto = _comm_protocol_from_prescription(pres, channel.get("protocol") or "")
    if proto in ("", "AUTO", "NONE"):
        return None

    merged = _merge_comm_params(channel, pres)
    merged["protocol"] = proto
    merged["channel_id"] = channel_id

    # Modbus acquisition requires register metadata; keep channel_id authoritative.
    if proto in ("MODBUS_TCP", "MODBUS_RTU"):
        if merged.get("register") in (None, "", "None"):
            return None
        if merged.get("function_code") in (None, "", "None"):
            merged["function_code"] = 4
        if merged.get("dtype") in (None, "", "None"):
            merged["dtype"] = "uint16"
        if merged.get("quantity") in (None, "", "None"):
            merged["quantity"] = 1
        if merged.get("scale") in (None, "", "None"):
            merged["scale"] = 1.0
        if merged.get("offset") in (None, "", "None"):
            merged["offset"] = 0.0
        return merged

    return None


@dataclass
class _Binding:
    code: str
    channel: Dict[str, Any]


class MappedModbusDriver:
    name = "MODBUS_MAPPED"

    def __init__(self, bindings: Iterable[_Binding]):
        self._bindings = list(bindings)
        self._last_ok = False

    def connect(self) -> None:
        return

    def close(self) -> None:
        return

    def read_all(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"ts_iso": _now_iso(), "comm_ok": False}
        ok_count = 0
        for binding in self._bindings:
            result = poll_modbus_channel(binding.channel)
            if result.ok and result.value_scaled is not None:
                out[binding.code] = round(float(result.value_scaled), 6)
                ok_count += 1
            else:
                out.setdefault("comm_errors", {})
                out["comm_errors"][binding.code] = result.message
        out["comm_ok"] = ok_count > 0
        self._last_ok = bool(out["comm_ok"])
        return out


def maybe_build_mapped_comm_driver(
    session: Dict[str, Any],
    *,
    poll_codes: Optional[Sequence[str]] = None,
    prescriptions: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[MappedModbusDriver]:
    cfg = _load_runtime_config()
    profile = _active_hardware_profile(cfg)
    channel_map = _merged_profile_channels(profile)

    poll = session.get("pollutants") or {}
    selected = list(poll_codes or []) or list(poll.get("selected") or [])
    pres = prescriptions or (poll.get("prescriptions") or {})
    if not isinstance(pres, dict):
        pres = {}

    bindings: List[_Binding] = []
    for code in selected:
        row = pres.get(code) if isinstance(pres.get(code), dict) else {}
        if not row:
            continue
        resolved = _resolve_binding(code, row, channel_map)
        if resolved is None:
            continue
        bindings.append(_Binding(code=code, channel=resolved))

    if not bindings:
        return None
    return MappedModbusDriver(bindings)
