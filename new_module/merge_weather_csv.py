#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class WeatherFileInfo:
    path: str
    filename: str
    start_date: datetime
    end_date: datetime


_SINGLE_DAY_RE = re.compile(r"^era5_(\d{4}-\d{2}-\d{2})\.csv$", re.IGNORECASE)
_RANGE_RE = re.compile(r"^era5_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.csv$", re.IGNORECASE)

# Tolerant patterns: allow 1-2 digit month/day (e.g. era5_2024-10-9_to_2024-10-10.csv)
_SINGLE_DAY_RE2 = re.compile(r"^era5_(\d{4})-(\d{1,2})-(\d{1,2})\.csv$", re.IGNORECASE)
_RANGE_RE2 = re.compile(r"^era5_(\d{4})-(\d{1,2})-(\d{1,2})_to_(\d{4})-(\d{1,2})-(\d{1,2})\.csv$", re.IGNORECASE)


def _parse_date_ymd(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def parse_weather_filename(filename: str) -> Optional[WeatherFileInfo]:
    m = _RANGE_RE.match(filename)
    if m:
        s0, s1 = m.group(1), m.group(2)
        d0, d1 = _parse_date_ymd(s0), _parse_date_ymd(s1)
        if d1 < d0:
            raise ValueError(f"Invalid date range in filename: {filename}")
        return WeatherFileInfo(path="", filename=filename, start_date=d0, end_date=d1)

    m = _SINGLE_DAY_RE.match(filename)
    if m:
        d0 = _parse_date_ymd(m.group(1))
        return WeatherFileInfo(path="", filename=filename, start_date=d0, end_date=d0)

    # tolerant patterns (1-2 digit month/day)
    m = _RANGE_RE2.match(filename)
    if m:
        y0, mo0, da0, y1, mo1, da1 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
        s0 = f"{int(y0):04d}-{int(mo0):02d}-{int(da0):02d}"
        s1 = f"{int(y1):04d}-{int(mo1):02d}-{int(da1):02d}"
        d0, d1 = _parse_date_ymd(s0), _parse_date_ymd(s1)
        if d1 < d0:
            raise ValueError(f"Invalid date range in filename: {filename}")
        return WeatherFileInfo(path="", filename=filename, start_date=d0, end_date=d1)

    m = _SINGLE_DAY_RE2.match(filename)
    if m:
        y0, mo0, da0 = m.group(1), m.group(2), m.group(3)
        s0 = f"{int(y0):04d}-{int(mo0):02d}-{int(da0):02d}"
        d0 = _parse_date_ymd(s0)
        return WeatherFileInfo(path="", filename=filename, start_date=d0, end_date=d0)

    return None


def list_weather_csvs(weather_dir: str) -> List[WeatherFileInfo]:
    files = []
    for name in os.listdir(weather_dir):
        if not name.lower().endswith('.csv'):
            continue
        # Skip non-data scripts
        if name.lower().startswith('test_'):
            continue
        info = parse_weather_filename(name)
        if info is None:
            continue
        files.append(WeatherFileInfo(
            path=os.path.join(weather_dir, name),
            filename=name,
            start_date=info.start_date,
            end_date=info.end_date,
        ))

    if not files:
        raise FileNotFoundError(f"No weather CSV files found under: {weather_dir}")

    files.sort(key=lambda x: (x.start_date, x.end_date, x.filename))
    return files


def _read_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if 'time' not in df.columns:
        raise KeyError(f"Missing 'time' column in {path}")
    df['time'] = pd.to_datetime(df['time'])
    return df


def _time_span(df: pd.DataFrame) -> Tuple[pd.Timestamp, pd.Timestamp]:
    t0 = df['time'].min()
    t1 = df['time'].max()
    return t0, t1


def merge_weather_csvs(weather_dir: str, output_csv: str) -> str:
    files = list_weather_csvs(weather_dir)

    # Read all, collect spans
    dfs: List[pd.DataFrame] = []
    spans: List[Tuple[str, pd.Timestamp, pd.Timestamp]] = []

    for f in files:
        df = _read_csv(f.path)
        t0, t1 = _time_span(df)
        spans.append((f.filename, t0, t1))
        dfs.append(df)

    # Check for overlaps/duplicates across files
    # Strategy: concatenate just (time, source_file), then detect duplicate 'time'
    time_parts = []
    for (fname, _, _), df in zip(spans, dfs):
        tmp = df[['time']].copy()
        tmp['__source_file__'] = fname
        time_parts.append(tmp)

    time_all = pd.concat(time_parts, ignore_index=True)
    dup_mask = time_all.duplicated(subset=['time'], keep=False)
    if dup_mask.any():
        dup = time_all.loc[dup_mask].sort_values('time')
        # Build a compact error message: show first N duplicated times with their files
        sample = dup.groupby('time')['__source_file__'].apply(lambda s: sorted(set(s.tolist()))).head(20)
        lines = ["Detected time conflicts (duplicate timestamps across CSV files).", "Sample (up to 20 timestamps):"]
        for ts, flist in sample.items():
            lines.append(f"- {ts}: {', '.join(flist)}")
        raise ValueError("\n".join(lines))

    # Union columns (outer) and merge
    merged = pd.concat(dfs, ignore_index=True, sort=False)

    # Sort by time, then by lat/lon/number if present for deterministic order
    sort_cols = ['time']
    for c in ['latitude', 'longitude', 'number']:
        if c in merged.columns:
            sort_cols.append(c)
    merged = merged.sort_values(sort_cols).reset_index(drop=True)

    os.makedirs(os.path.dirname(output_csv) or '.', exist_ok=True)
    merged.to_csv(output_csv, index=False, encoding='utf-8')

    return output_csv


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    weather_dir = 'weather'
    output_csv = os.path.join(weather_dir, 'era5_merged.csv')

    if len(argv) >= 1:
        weather_dir = argv[0]
    if len(argv) >= 2:
        output_csv = argv[1]

    out = merge_weather_csvs(weather_dir, output_csv)
    print(f"Merged CSV written to: {out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
