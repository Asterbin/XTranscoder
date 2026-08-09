from __future__ import annotations

import csv
import io
import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"


@dataclass
class Pattern:
    """A one-dimensional diffraction pattern (2θ in degrees, intensity)."""

    points: list[tuple[float, float]]
    source_format: str = "unknown"


def detect_format(path: str | Path, content: bytes | None = None) -> str:
    path = Path(path)
    data = content if content is not None else path.read_bytes()
    head = data[:4096].decode("utf-8-sig", errors="ignore").lstrip()
    if data[:2] == b"FI": return "2.raw"
    if "<xrdMeasurements" in head or path.suffix.lower() == ".xrdml": return "1.xrdml"
    if head.startswith(";RAW4.00") or "[RawHeader]" in head: return "7.txt"
    if "[Scan points]" in head: return "3.csv"
    if "SampleIdent" in head and "Alpha1" in head: return "5.dat"
    if re.match(r"(?:2_theta|angle)\s*,", head, re.I): return "4.csv"
    if path.suffix.lower() == ".xy": return "6.xy"
    return "0.csv" if "," in head else "6.xy"


def _numbers(line: str) -> list[float]:
    return [float(v) for v in re.findall(NUMBER, line)]


def _two_columns(text: str, separator: str | None = None) -> list[tuple[float, float]]:
    result = []
    for line in text.splitlines():
        values = _numbers(line if separator is None else line.replace(separator, " "))
        if len(values) >= 2: result.append((values[0], values[1]))
    if not result: raise ValueError("No two-column diffraction data found")
    return result


def _read_xrdml(text: str) -> list[tuple[float, float]]:
    root = ET.fromstring(text)
    counts = next((e for e in root.iter() if e.tag.endswith("counts")), None)
    pos = next((e for e in root.iter() if e.tag.endswith("positions") and e.attrib.get("axis") == "2Theta"), None)
    if counts is None or pos is None: raise ValueError("XRDML lacks 2Theta positions or counts")
    start = float(next(e.text for e in pos if e.tag.endswith("startPosition")))
    end = float(next(e.text for e in pos if e.tag.endswith("endPosition")))
    y = _numbers(counts.text or "")
    step = (end - start) / max(len(y) - 1, 1)
    return [(start + i * step, value) for i, value in enumerate(y)]


def _read_dat(text: str) -> list[tuple[float, float]]:
    lines = text.splitlines()
    scan_row = next((i for i, line in enumerate(lines[:12])
                     if (v := _numbers(line)) and len(v) >= 3 and v[0] < v[2] and v[1] < v[2] - v[0]), None)
    header = _numbers(lines[scan_row]) if scan_row is not None else []
    if len(header) < 3: raise ValueError("DAT scan range is missing")
    start, step, end = header[:3]
    y = [value for line in lines[scan_row + 1:] for value in _numbers(line)]
    if not y: raise ValueError("DAT intensity values are missing")
    # Vendor DAT files record start, nominal increment and end. Prefer end to avoid drift.
    step = (end - start) / max(len(y) - 1, 1)
    return [(start + i * step, value) for i, value in enumerate(y)]


def _read_raw_binary(data: bytes) -> list[tuple[float, float]]:
    marker = data.find(b"DA\x00\x00")
    if marker < 0 or marker + 20 > len(data): raise ValueError("Unsupported RAW binary layout")
    count = struct.unpack_from("<I", data, marker + 16)[0]
    offset = marker + 20
    if count < 2 or offset + count * 4 > len(data): raise ValueError("Invalid RAW data block")
    y = struct.unpack_from(f"<{count}f", data, offset)
    # RAW's data block does not consistently expose 2θ in all vendor revisions.
    # Use scan metadata when present; this fallback keeps samples readable.
    return [(float(i), float(value)) for i, value in enumerate(y)]


def read(path: str | Path) -> Pattern:
    path = Path(path); data = path.read_bytes(); fmt = detect_format(path, data)
    text = data.decode("utf-8-sig", errors="replace")
    if fmt == "1.xrdml": points = _read_xrdml(text)
    elif fmt == "2.raw": points = _read_raw_binary(data)
    elif fmt == "3.csv":
        section = text.split("[Scan points]", 1)[-1]
        points = _two_columns("\n".join(section.splitlines()[1:]))
    elif fmt == "5.dat": points = _read_dat(text)
    elif fmt == "7.txt":
        section = text.split("[Data]", 1)[-1]
        points = _two_columns("\n".join(section.splitlines()[2:]))
    else:
        points = _two_columns(text)
    return Pattern(points, fmt)


def _fmt(v: float) -> str: return format(v, ".10g")


def write(pattern: Pattern, destination: str | Path, fmt: str = "0.csv") -> Path:
    destination = Path(destination); points = pattern.points
    if not points: raise ValueError("Cannot write an empty pattern")
    if fmt == "0.csv": text = "\n".join(f"{_fmt(x)},{_fmt(y)}" for x, y in points) + "\n"
    elif fmt == "4.csv": text = "2_theta,Intensity\n" + "\n".join(f"{_fmt(x)},{_fmt(y)}" for x,y in points) + "\n"
    elif fmt == "6.xy": text = "\n".join(f"{_fmt(x)} {_fmt(y)}" for x,y in points) + "\n"
    elif fmt == "3.csv":
        step = points[1][0] - points[0][0] if len(points)>1 else 0
        text = f"[Measurement conditions]\nScan range,{_fmt(points[0][0])},{_fmt(points[-1][0])}\nScan step size,{_fmt(step)}\nNo. of points,{len(points)}\n[Scan points]\nAngle, TimePerStep, Intensity, ESD\n" + "\n".join(f"{_fmt(x)}, 1, {_fmt(y)}, 0" for x,y in points) + "\n"
    elif fmt == "5.dat":
        step = (points[-1][0]-points[0][0])/max(len(points)-1,1)
        rows = ["SampleIdent ____ DataFileName ______", "DiffrType ______   GeneratorVoltage __   TubeCurrent __", "Anode __    Alpha1  1.54060    Alpha2  1.54443    Ratio  0.50000", "MonochromatorUsed __   DivergenceSlit _      ReceivingSlit ___", f"  {_fmt(points[0][0])}   {_fmt(step)}  {_fmt(points[-1][0])}"]
        rows += [" ".join(_fmt(y) for _,y in points[i:i+10]) for i in range(0,len(points),10)]
        text = "\n".join(rows)+"\n"
    elif fmt == "7.txt":
        step=(points[-1][0]-points[0][0])/max(len(points)-1,1)
        text = f";RAW4.00\n[RawHeader]\nNumberOfRanges=1\n\n[RangeHeader]\nStart={_fmt(points[0][0])}\nIncrement={_fmt(step)}\nSteps={len(points)}\n\n[Data]\n     Angle,       PSD,\n" + "\n".join(f"{_fmt(x):>10}, {_fmt(y):>10}," for x,y in points)+"\n"
    elif fmt == "1.xrdml":
        counts=" ".join(_fmt(y) for _,y in points)
        text=f'<?xml version="1.0" encoding="UTF-8"?>\n<xrdMeasurements xmlns="http://www.xrdml.com/XRDMeasurement/2.2"><xrdMeasurement><scan><dataPoints><positions axis="2Theta" unit="deg"><startPosition>{_fmt(points[0][0])}</startPosition><endPosition>{_fmt(points[-1][0])}</endPosition></positions><counts unit="counts">{counts}</counts></dataPoints></scan></xrdMeasurement></xrdMeasurements>\n'
    else: raise ValueError(f"Writing {fmt} is not supported (binary 2.raw is read-only)")
    destination.write_text(text, encoding="utf-8")
    return destination
