from __future__ import annotations

import os
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from mole_modbus_codec_v1 import decode_words, dtype_register_count, normalize_dtype


@dataclass
class ModbusPollResult:
    ok: bool
    protocol: str
    address: Optional[int]
    raw_words: List[int]
    value_raw: Optional[float]
    value_scaled: Optional[float]
    message: str
    elapsed_ms: float
    diagnostics: Dict[str, Any]


class ModbusPollError(RuntimeError):
    def __init__(self, message: str, diagnostics: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


def list_serial_ports() -> List[str]:
    ports: List[str] = []
    try:
        if os.name == "nt":
            import winreg  # type: ignore

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
            idx = 0
            while True:
                try:
                    _name, value, _kind = winreg.EnumValue(key, idx)
                except OSError:
                    break
                idx += 1
                text = str(value or "").strip()
                if text:
                    ports.append(text)
    except Exception:
        ports = []
    return sorted(set(ports))


def register_to_zero_based(register: Any, function_code: Any) -> int:
    reg = int(float(register))
    fc = int(float(function_code))
    if fc == 4 and reg >= 30001:
        return reg - 30001
    if fc == 3 and reg >= 40001:
        return reg - 40001
    if reg >= 1:
        return reg - 1
    return reg


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _crc16_modbus(payload: bytes) -> int:
    crc = 0xFFFF
    for ch in payload:
        crc ^= ch
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def _scale_value(value: float | int, scale: Any, offset: Any) -> float:
    scale_f = _coerce_float(scale, 1.0)
    offset_f = _coerce_float(offset, 0.0)
    return (float(value) * scale_f) + offset_f


def _hex_preview(payload: bytes, *, limit: int = 24) -> str:
    if not payload:
        return ""
    clip = payload[:limit]
    text = " ".join(f"{b:02X}" for b in clip)
    if len(payload) > limit:
        text += " ..."
    return text


def _hex_full(payload: bytes) -> str:
    if not payload:
        return ""
    return " ".join(f"{b:02X}" for b in payload)


def _poll_tcp(
    *,
    host: str,
    port: int,
    unit_id: int,
    function_code: int,
    zero_based_address: int,
    quantity: int,
    timeout_s: float,
) -> List[int]:
    tx_id = int(time.time() * 1000) & 0xFFFF
    pdu = struct.pack(">BHH", function_code, zero_based_address, quantity)
    mbap = struct.pack(">HHHB", tx_id, 0, len(pdu) + 1, unit_id)
    frame = mbap + pdu

    with socket.create_connection((host, port), timeout=timeout_s) as sock:
        sock.settimeout(timeout_s)
        sock.sendall(frame)
        header = sock.recv(7)
        if len(header) < 7:
            raise RuntimeError("Short MBAP header")
        rx_tx_id, _proto_id, length, _uid = struct.unpack(">HHHB", header)
        if rx_tx_id != tx_id:
            raise RuntimeError("Transaction ID mismatch")
        remaining = length - 1
        payload = b""
        while len(payload) < remaining:
            chunk = sock.recv(remaining - len(payload))
            if not chunk:
                break
            payload += chunk
        if len(payload) < 2:
            raise RuntimeError("Short Modbus response")
        fc = payload[0]
        if fc & 0x80:
            code = payload[1] if len(payload) > 1 else -1
            raise RuntimeError(f"Modbus exception code {code}")
        byte_count = payload[1]
        data = payload[2 : 2 + byte_count]
        if len(data) != byte_count:
            raise RuntimeError("Incomplete register payload")
        if byte_count % 2 != 0:
            raise RuntimeError("Odd register byte count")
        return list(struct.unpack(">" + ("H" * (byte_count // 2)), data))


def _poll_rtu(
    *,
    serial_port: str,
    baud: int,
    parity: str,
    stopbits: str,
    unit_id: int,
    function_code: int,
    zero_based_address: int,
    quantity: int,
    timeout_s: float,
    retries: int = 2,
    inter_request_delay_s: float = 0.02,
    open_settle_s: float = 0.02,
) -> tuple[List[int], Dict[str, Any]]:
    try:
        import serial  # type: ignore
    except Exception as exc:
        raise RuntimeError("pyserial not installed; RTU polling unavailable") from exc

    frame = struct.pack(">BBHH", unit_id, function_code, zero_based_address, quantity)
    crc = _crc16_modbus(frame)
    req = frame + struct.pack("<H", crc)
    diagnostics: Dict[str, Any] = {
        "transport": "RTU",
        "serial_port": serial_port,
        "baud": baud,
        "parity": str(parity).strip().upper(),
        "stopbits": str(stopbits).strip(),
        "unit_id": unit_id,
        "function_code": function_code,
        "request_zero_based_address": zero_based_address,
        "request_quantity": quantity,
        "request_hex": _hex_full(req),
        "retries": max(1, int(retries)),
        "inter_request_delay_s": inter_request_delay_s,
        "open_settle_s": open_settle_s,
        "attempt_log": [],
    }

    stopbits_obj = serial.STOPBITS_ONE if str(stopbits).strip() != "2" else serial.STOPBITS_TWO
    bytesize_obj = serial.EIGHTBITS
    parity_obj = {
        "N": serial.PARITY_NONE,
        "E": serial.PARITY_EVEN,
        "O": serial.PARITY_ODD,
    }.get(str(parity).strip().upper(), serial.PARITY_NONE)

    ser = serial.Serial(
        port=serial_port,
        baudrate=baud,
        bytesize=bytesize_obj,
        parity=parity_obj,
        stopbits=stopbits_obj,
        timeout=timeout_s,
        inter_byte_timeout=min(max(timeout_s * 0.25, 0.05), timeout_s) if timeout_s > 0 else 0.1,
    )
    try:
        if open_settle_s > 0:
            time.sleep(open_settle_s)
        last_error = "Short RTU response"
        attempts = max(1, int(retries))
        for attempt in range(attempts):
            attempt_info: Dict[str, Any] = {"attempt": attempt + 1}
            try:
                ser.reset_input_buffer()
            except Exception:
                pass
            try:
                ser.reset_output_buffer()
            except Exception:
                pass
            if attempt and inter_request_delay_s > 0:
                time.sleep(inter_request_delay_s)
            ser.write(req)
            try:
                ser.flush()
            except Exception:
                pass

            expected = 5 + (2 * quantity)
            attempt_info["expected_bytes_initial"] = expected
            resp = b""
            deadline = time.time() + max(timeout_s, 0.25)
            while len(resp) < expected and time.time() < deadline:
                chunk = ser.read(expected - len(resp))
                if not chunk:
                    break
                resp += chunk
                if len(resp) >= 3:
                    fc = resp[1]
                    byte_count = resp[2]
                    if fc & 0x80:
                        expected = 5
                    else:
                        expected = 5 + int(byte_count)
                    deadline = max(deadline, time.time() + 0.05)
            attempt_info["expected_bytes_final"] = expected
            attempt_info["response_len"] = len(resp)
            attempt_info["response_hex"] = _hex_full(resp)
            if len(resp) < 5:
                preview = _hex_preview(resp)
                last_error = f"Short RTU response ({len(resp)} byte(s){': ' + preview if preview else ''})"
                attempt_info["error"] = last_error
                diagnostics["attempt_log"].append(attempt_info)
                continue
            body = resp[:-2]
            rx_crc = struct.unpack("<H", resp[-2:])[0]
            calc_crc = _crc16_modbus(body)
            if rx_crc != calc_crc:
                preview = _hex_preview(resp)
                last_error = f"RTU CRC mismatch ({preview})"
                attempt_info["error"] = last_error
                diagnostics["attempt_log"].append(attempt_info)
                continue
            addr, fc, byte_count = struct.unpack(">BBB", body[:3])
            if addr != unit_id:
                last_error = f"RTU unit ID mismatch (got {addr}, expected {unit_id})"
                attempt_info["error"] = last_error
                diagnostics["attempt_log"].append(attempt_info)
                continue
            if fc & 0x80:
                code = body[2] if len(body) > 2 else -1
                last_error = f"Modbus exception code {code}"
                attempt_info["error"] = last_error
                diagnostics["attempt_log"].append(attempt_info)
                raise ModbusPollError(last_error, diagnostics=diagnostics)
            data = body[3:]
            if len(data) != byte_count:
                last_error = f"Incomplete RTU register payload ({len(data)}/{byte_count} bytes)"
                attempt_info["error"] = last_error
                diagnostics["attempt_log"].append(attempt_info)
                continue
            if byte_count % 2 != 0:
                last_error = "Odd RTU register byte count"
                attempt_info["error"] = last_error
                diagnostics["attempt_log"].append(attempt_info)
                raise ModbusPollError(last_error, diagnostics=diagnostics)
            attempt_info["byte_count"] = byte_count
            diagnostics["attempt_log"].append(attempt_info)
            diagnostics["response_hex"] = _hex_full(resp)
            diagnostics["response_len"] = len(resp)
            diagnostics["expected_bytes_final"] = expected
            diagnostics["attempts_used"] = attempt + 1
            return list(struct.unpack(">" + ("H" * (byte_count // 2)), data)), diagnostics
        diagnostics["response_hex"] = diagnostics["attempt_log"][-1].get("response_hex", "") if diagnostics["attempt_log"] else ""
        diagnostics["response_len"] = diagnostics["attempt_log"][-1].get("response_len", 0) if diagnostics["attempt_log"] else 0
        diagnostics["expected_bytes_final"] = diagnostics["attempt_log"][-1].get("expected_bytes_final", 0) if diagnostics["attempt_log"] else 0
        diagnostics["attempts_used"] = attempts
        diagnostics["last_error"] = last_error
        raise ModbusPollError(last_error, diagnostics=diagnostics)
    finally:
        try:
            ser.close()
        except Exception:
            pass


def poll_modbus_channel(channel: Dict[str, Any]) -> ModbusPollResult:
    started = time.time()
    protocol = str(channel.get("protocol") or "MODBUS_TCP").strip().upper()
    function_code = _coerce_int(channel.get("function_code"), 4)
    dtype = normalize_dtype(channel.get("dtype") or "uint16")
    target_quantity = _coerce_int(channel.get("quantity"), dtype_register_count(dtype))
    timeout_s = _coerce_float(channel.get("timeout_s"), 2.0)
    target_register = _coerce_int(channel.get("register"), 0)
    zero_based = register_to_zero_based(target_register, function_code)
    block_register_raw = channel.get("block_register")
    use_block_window = block_register_raw not in (None, "", "None")
    read_register = _coerce_int(block_register_raw, target_register) if use_block_window else target_register
    read_quantity = _coerce_int(channel.get("block_quantity"), target_quantity) if use_block_window else target_quantity
    read_zero_based = register_to_zero_based(read_register, function_code)
    words: List[int] = []
    diagnostics: Dict[str, Any] = {
        "protocol": protocol,
        "target_register": target_register,
        "target_quantity": target_quantity,
        "target_zero_based_address": zero_based,
        "read_register": read_register,
        "read_quantity": read_quantity,
        "read_zero_based_address": read_zero_based,
        "dtype": dtype,
        "block_window": use_block_window,
        "block_word_index": _coerce_int(channel.get("block_word_index"), max(0, zero_based - read_zero_based)) if use_block_window else 0,
    }
    try:
        unit_id = _coerce_int(channel.get("unit_id"), 1)
        diagnostics["unit_id"] = unit_id
        if protocol == "MODBUS_TCP":
            host = str(channel.get("host") or "").strip()
            port = _coerce_int(channel.get("port"), 502)
            if not host:
                raise RuntimeError("Missing host")
            diagnostics["host"] = host
            diagnostics["port"] = port
            words = _poll_tcp(
                host=host,
                port=port,
                unit_id=unit_id,
                function_code=function_code,
                zero_based_address=read_zero_based,
                quantity=read_quantity,
                timeout_s=timeout_s,
            )
        elif protocol == "MODBUS_RTU":
            serial_port = str(channel.get("serial_port") or "").strip()
            if not serial_port:
                raise RuntimeError("Missing serial_port")
            diagnostics["serial_port"] = serial_port
            diagnostics["baud"] = _coerce_int(channel.get("baud"), 9600)
            diagnostics["parity"] = str(channel.get("parity") or "N")
            diagnostics["stopbits"] = str(channel.get("stopbits") or "1")
            words, rtu_diag = _poll_rtu(
                serial_port=serial_port,
                baud=diagnostics["baud"],
                parity=diagnostics["parity"],
                stopbits=diagnostics["stopbits"],
                unit_id=unit_id,
                function_code=function_code,
                zero_based_address=read_zero_based,
                quantity=read_quantity,
                timeout_s=timeout_s,
                retries=_coerce_int(channel.get("retries"), 2),
                inter_request_delay_s=_coerce_float(channel.get("inter_request_delay_s"), 0.02),
                open_settle_s=_coerce_float(channel.get("open_settle_s"), 0.02),
            )
            diagnostics.update(rtu_diag)
        else:
            raise RuntimeError(f"Unsupported Modbus protocol: {protocol}")

        selected_words = words
        if use_block_window:
            word_index = _coerce_int(
                channel.get("block_word_index"),
                max(0, zero_based - read_zero_based),
            )
            need = dtype_register_count(dtype)
            selected_words = words[word_index : word_index + need]
            if len(selected_words) < need:
                raise RuntimeError(
                    f"Block window incomplete for target register {target_register} "
                    f"(need {need} word(s) at offset {word_index}, got {len(selected_words)})"
                )
        raw = decode_words(selected_words, dtype)
        scaled = _scale_value(raw, channel.get("scale"), channel.get("offset"))
        elapsed_ms = (time.time() - started) * 1000.0
        if use_block_window:
            message = (
                f"OK (window {read_register} qty {read_quantity}, "
                f"target {target_register} offset {max(0, zero_based - read_zero_based)})"
            )
        else:
            message = "OK"
        return ModbusPollResult(
            ok=True,
            protocol=protocol,
            address=zero_based,
            raw_words=selected_words,
            value_raw=float(raw),
            value_scaled=float(scaled),
            message=message,
            elapsed_ms=elapsed_ms,
            diagnostics=diagnostics,
        )
    except ModbusPollError as exc:
        elapsed_ms = (time.time() - started) * 1000.0
        if getattr(exc, "diagnostics", None):
            diagnostics.update(exc.diagnostics)
        return ModbusPollResult(
            ok=False,
            protocol=protocol,
            address=zero_based,
            raw_words=words,
            value_raw=None,
            value_scaled=None,
            message=str(exc),
            elapsed_ms=elapsed_ms,
            diagnostics=diagnostics,
        )
    except Exception as exc:
        elapsed_ms = (time.time() - started) * 1000.0
        return ModbusPollResult(
            ok=False,
            protocol=protocol,
            address=zero_based,
            raw_words=words,
            value_raw=None,
            value_scaled=None,
            message=str(exc),
            elapsed_ms=elapsed_ms,
            diagnostics=diagnostics,
        )
