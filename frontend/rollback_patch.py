import sys
import re

path = r"C:\Users\hongji.huang\OneDrive - PBA Systems Pte. Ltd\Desktop\BOM_Component__DWG_Mgmt\backend\BOM_Backend_API.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

old_func_pattern = r'def _parse_bom_rows.*?return final_cols, df\.to_dict\(orient="records"\)'
if not re.search(old_func_pattern, text, re.DOTALL):
    # try an alternative pattern if the end changed
    old_func_pattern = r'def _parse_bom_rows.*?return columns, rows\s*'

new_func = '''def _parse_bom_rows(contents: bytes, extension: str) -> tuple[list[str], list[dict]]:
    """Parse BOM content in a worker thread. Dynamically detects header row in Excel to avoid Unnamed columns."""
    stream = io.BytesIO(contents)

    if extension == ".csv":
        df = pd.read_csv(stream, keep_default_na=False, na_filter=False)
    else:
        preview_df = pd.read_excel(stream, engine="openpyxl", header=None, nrows=40, keep_default_na=False, na_filter=False)
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

    final_cols = []
    seen = set()
    for i, col in enumerate(df.columns.tolist()):
        c_str = str(col).strip()
        if "Unnamed" in c_str or not c_str:
            c_str = f"Col_{i+1}"
        # Make column unique
        base = c_str
        count = 1
        while c_str in seen:
            c_str = f"{base}_{count}"
            count += 1
        seen.add(c_str)
        final_cols.append(c_str)
        
    df.columns = final_cols

    # Drop entirely empty rows gracefully (since we used keep_default_na=False, empty is "")
    if not df.empty:
        mask = (df != "").any(axis=1)
        df = df.loc[mask]

    columns = final_cols
    rows = df.to_dict(orient="records")
    return columns, rows'''

text = re.sub(old_func_pattern, new_func, text, flags=re.DOTALL, count=1)
with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Rollback applied.")
