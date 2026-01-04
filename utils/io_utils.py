"""File IO helpers."""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pandas as pd


def safe_read_file(file_path: str, is_csv: bool = False):
    """Safely read file with encoding auto-detection.

    Args:
        file_path: file path
        is_csv: whether to treat as CSV (pandas)

    Returns:
        numpy array
    """
    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'ascii', 'latin1']

    for encoding in encodings:
        try:
            if is_csv:
                df = pd.read_csv(file_path, encoding=encoding, sep=None, engine='python')
                return df.to_numpy()

            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()

            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                data = np.loadtxt(temp_file_path)
                os.unlink(temp_file_path)
                return data
            except Exception:
                os.unlink(temp_file_path)
                continue

        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            continue

    # fallback: ignore errors
    if is_csv:
        df = pd.read_csv(file_path, encoding='utf-8', errors='ignore', sep=None, engine='python')
        return df.to_numpy()

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        data_lines = []
        for line in lines:
            line = line.strip()
            if line and (not line.startswith('#')) and (not line.startswith(';')):
                try:
                    values = [float(x) for x in line.split()]
                    if len(values) >= 2:
                        data_lines.append(values[:2])
                except ValueError:
                    continue

        if data_lines:
            return np.array(data_lines)
        raise Exception('无法从文件中解析出有效数据')

    except Exception as e:
        raise Exception(f"无法读取文件 {file_path}: {str(e)}")


def validate_data_file(file_path: str, min_rows: int = 10) -> bool:
    """Validate basic shape of a numeric data file."""
    try:
        data = safe_read_file(file_path)
        if data.shape[0] < min_rows:
            return False
        if data.shape[1] < 2:
            return False
        return True
    except Exception:
        return False
