from __future__ import annotations

import io

import numpy as np
import pandas as pd


def parse_bom_rows(contents: bytes, extension: str) -> tuple[list[str], list[dict]]:
    """Parse BOM content and infer the best Excel header row."""
    stream = io.BytesIO(contents)

    def get_excel_col_name(n: int) -> str:
        res = ""
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            res = chr(65 + remainder) + res
        return res

    if extension == ".csv":
        df = pd.read_csv(stream, keep_default_na=False, na_filter=False)
    else:
        preview_df = pd.read_excel(
            stream,
            engine="openpyxl",
            header=None,
            nrows=40,
            keep_default_na=False,
            na_filter=False,
        )
        best_header_idx = 0
        max_score = -1

        for idx, row in preview_df.iterrows():
            row_strs = [str(x).strip().upper() for x in row.values if str(x).strip()]
            score = len(row_strs)
            for kw in ["PARENT", "COMPONENT", "PART", "ITEM", "DESC", "LEVEL", "QTY", "QUANTITY"]:
                if any(kw in s for s in row_strs):
                    score += 15
            if score > max_score:
                max_score = score
                best_header_idx = idx

        stream.seek(0)
        df = pd.read_excel(
            stream,
            engine="openpyxl",
            header=best_header_idx,
            keep_default_na=False,
            na_filter=False,
        )

    final_cols: list[str] = []
    seen: set[str] = set()
    for i, col in enumerate(df.columns.tolist()):
        c_str = str(col).strip()
        excel_col_letter = get_excel_col_name(i + 1)

        if "Unnamed" in c_str or not c_str:
            c_str = f"column_{excel_col_letter}"

        base = c_str
        count = 1
        while c_str in seen:
            c_str = f"{base}_{count}"
            count += 1
        seen.add(c_str)
        final_cols.append(c_str)

    df.columns = final_cols

    error_patterns = [r"^#N/A", r"^#DIV/0!", r"^#VALUE!", r"^#REF!", r"^#NAME\?", r"^#NUM!"]
    df = df.replace(to_replace=error_patterns, value="", regex=True)
    df = df.replace([np.nan, float("inf"), float("-inf")], "")
    df = df.fillna("")

    if not df.empty:
        mask = (df != "").any(axis=1)
        df = df.loc[mask]

    columns = final_cols
    rows = df.to_dict(orient="records")
    return columns, rows
