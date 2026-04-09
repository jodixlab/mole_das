from __future__ import annotations

import dataclasses
import hashlib
import base64
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import tkinter as tk

try:
    # Optional: nicer scaling/decoding
    from PIL import Image, ImageTk  # type: ignore
except Exception:  # pragma: no cover
    Image = None
    ImageTk = None


@dataclasses.dataclass
class MapStatus:
    ok: bool
    message: str
    cache_hit: bool = False


class StaticMapWidget:
    """Small static-map image widget.

    Uses the public OSM static map endpoint (staticmap.openstreetmap.de).

    Works with or without Pillow:
      - With Pillow: decodes/resizes via PIL for consistent sizing.
      - Without Pillow: uses tk.PhotoImage with base64 PNG data (no resize).
        (We request the exact size from the endpoint so resize is not required.)
    """

    def __init__(
        self,
        parent: tk.Widget,
        cache_dir: Path,
        width: int = 520,
        height: int = 260,
        zoom: int = 15,
        bg: str = "#0e1116",
    ) -> None:
        self.parent = parent
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.width = int(width)
        self.height = int(height)
        self.zoom = int(zoom)
        self.bg = bg

        self.frame = tk.Frame(parent, bg=bg)
        self._label = tk.Label(self.frame, bg=bg)
        self._label.pack(fill="x")

        self._tk_img = None  # keep reference

    def set_coords(self, lat: float, lon: float) -> MapStatus:
        """Fetch (or load cached) map image and render it."""
        try:
            lat = float(lat)
            lon = float(lon)
        except Exception:
            return MapStatus(False, "invalid coords")

        key = self._cache_key(lat, lon)
        png_path = self.cache_dir / f"map_{key}.png"

        cache_hit = png_path.exists()
        if not cache_hit:
            ok, msg = self._download(png_path, lat, lon)
            if not ok:
                return MapStatus(False, msg, cache_hit=False)

        try:
            data = png_path.read_bytes()
            if Image is not None and ImageTk is not None:
                img = Image.open(png_path)
                img = img.resize((self.width, self.height))
                self._tk_img = ImageTk.PhotoImage(img)
            else:
                # Tk can load PNG data when provided as base64 string.
                b64 = base64.b64encode(data)
                self._tk_img = tk.PhotoImage(data=b64)
            self._label.configure(image=self._tk_img)
            return MapStatus(True, "ok" + (" (cached)" if cache_hit else ""), cache_hit=cache_hit)
        except Exception:
            return MapStatus(False, "decode failed", cache_hit=cache_hit)

    def _cache_key(self, lat: float, lon: float) -> str:
        raw = f"{lat:.6f},{lon:.6f},z{self.zoom},w{self.width},h{self.height}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()[:16]

    def _download(self, path: Path, lat: float, lon: float) -> tuple[bool, str]:
        """Download map PNG using a provider fallback chain.

        Providers:
          1) staticmap.openstreetmap.de (OSM static)
          2) ArcGIS Online World_Street_Map export (no key)

        Notes:
          - If DNS or outbound HTTP(S) is blocked, all providers may fail.
          - Caller should expose the error and offer "Open in Browser" fallback.
        """
        # Provider 1: OSM static
        ok, msg = self._download_osm_static(path, lat, lon)
        if ok:
            return True, msg

        # Provider 2: ESRI export fallback
        ok2, msg2 = self._download_esri_export(path, lat, lon)
        if ok2:
            return True, msg2

        # Return the most informative message
        return False, msg if msg else msg2

    def _download_osm_static(self, path: Path, lat: float, lon: float) -> tuple[bool, str]:
        try:
            params = {
                "center": f"{lat:.6f},{lon:.6f}",
                "zoom": str(self.zoom),
                "size": f"{self.width}x{self.height}",
                "maptype": "mapnik",
                "markers": f"{lat:.6f},{lon:.6f},red-pushpin",
            }
            url = "https://staticmap.openstreetmap.de/staticmap.php?" + urlencode(params)
            req = Request(url, headers={"User-Agent": "MOLE-DAS"})
            with urlopen(req, timeout=10) as resp:
                data = resp.read()
            path.write_bytes(data)
            if path.stat().st_size < 800:
                return False, "OSM download too small"
            return True, "downloaded (OSM)" 
        except Exception as e:
            return False, f"OSM download failed: {e}"

    def _download_esri_export(self, path: Path, lat: float, lon: float) -> tuple[bool, str]:
        """ArcGIS Online export endpoint (no key) for a static map image."""
        try:
            # WebMercator-ish ground resolution (m/px) at latitude
            # https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
            res_m_per_px = 156543.03392 * math.cos(math.radians(lat)) / (2 ** self.zoom)
            half_w_m = res_m_per_px * (self.width / 2.0)
            half_h_m = res_m_per_px * (self.height / 2.0)

            # meters -> degrees
            m_per_deg_lat = 111320.0
            m_per_deg_lon = 111320.0 * max(0.01, math.cos(math.radians(lat)))

            dlat = half_h_m / m_per_deg_lat
            dlon = half_w_m / m_per_deg_lon

            xmin = lon - dlon
            xmax = lon + dlon
            ymin = lat - dlat
            ymax = lat + dlat

            params = {
                "bbox": f"{xmin:.6f},{ymin:.6f},{xmax:.6f},{ymax:.6f}",
                "bboxSR": "4326",
                "size": f"{self.width},{self.height}",
                "format": "png",
                "f": "image",
                "imageSR": "4326",
            }
            url = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/export?" + urlencode(params)
            req = Request(url, headers={"User-Agent": "MOLE-DAS"})
            with urlopen(req, timeout=10) as resp:
                data = resp.read()
            path.write_bytes(data)
            if path.stat().st_size < 800:
                return False, "ESRI download too small"
            return True, "downloaded (ESRI)" 
        except Exception as e:
            return False, f"ESRI download failed: {e}"
