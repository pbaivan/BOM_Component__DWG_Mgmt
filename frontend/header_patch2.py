import sys
path = r"C:\Users\hongji.huang\OneDrive - PBA Systems Pte. Ltd\Desktop\BOM_Component__DWG_Mgmt\backend\BOM_Backend_API.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

import re
old_func_pattern = r'def _parse_bom_rows.*?return columns, rows'
if not re.search(old_func_pattern, text, re.DOTALL):
    print("Function not found!")
    sys.exit(1)

new_func = '''def _parse_bom_rows(contents: bytes, extension: str) -> tuple[list[str], list[dict]]:
    """Parse BOM content in a worker thread. Dynamically detects header row in Excel to avoid Unnamed columns."""
    stream = io.BytesIO(contents)

    if extension == ".csv":
        df = pd.read_csv(stream, keep_default_na=False, na_filter=False)
    else:
        preview_df = pd.read_excel(stream, engine="openpyxl", header=None, nrows=35, keep_default_na=False, na_filter=False)
        best_header_idx = -1
        
        kws = {"PARENT", "COMPONENT", "PART", "ITEM", "DESCR", "LEVEL", "QTY", "QUANTITY", "REV", "MAT", "VENDOR", "REMARK"}
        
        for idx, row in preview_df.iterrows():
            row_strs = [str(x).strip().upper() for x in row.values if str(x).strip()]
            if not row_strs:
                continue
                
            # If a row has strong BOM-related keywords, assume it's the header and stop immediately.
            if any(any(kw in s for kw in kws) for s in row_strs):
                best_header_idx = idx
                break
                
        # Fallback: If no keywords matched, pick the first row that has at least 2 non-blank cells (skipping titles/blanks)
        if best_header_idx == -1:
            for idx, row in preview_df.iterrows():
                row_strs = [str(x).strip() for x in row.values if str(x).strip()]
                if len(row_strs) >= 2:
                    best_header_idx = idx
                    break
                    
        if best_header_idx == -1:
            best_header_idx = 0

        stream.seek(0)
        df = pd.read_excel(
            stream,
            engine="openpyxl",
            header=best_header_idx,
            keep_default_na=False,
            na_filter=False,
        )

    cols_to_keep = []
    final_cols = []
    seen = set()

    for i, col in enumerate(df.columns.tolist()):
        c_str = str(col).strip()
        is_unnamed = "Unnamed:" in c_str or not c_str
        
        # Drop entirely empty unnamed "ghost" columns
        if is_unnamed and (df[col] == "").all():
            continue
            
        if is_unnamed:
            c_str = f"Col_{i+1}"
            
        # Make column unique
        base = c_str
        count = 1
        while c_str in seen:
            c_str = f"{base}_{count}"
            count += 1
        seen.add(c_str)
        
        cols_to_keep.append(col)
        final_cols.append(c_str)
        
    df = df[cols_to_keep]
    df.columns = final_cols

    # Drop entirely empty rows gracefully (since we used keep_default_na=False, empty is "")
    if not df.empty:
        mask = (df != "").any(axis=1)
        df = df.loc[mask]

    return final_cols, df.to_dict(orient="records")'''

text = re.sub(old_func_pattern, new_func, text, flags=re.DOTALL, count=1)
with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Regex replace applied.")
