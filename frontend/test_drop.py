import pandas as pd
import io

df = pd.DataFrame({
    "PARENT": ["A", "B"],
    "COMPONENT": ["X", "Y"],
    "Unnamed: 2": ["", ""],
    "": ["", ""]
})

cols_to_keep = []
for col in df.columns:
    c_str = str(col).strip()
    if "Unnamed" in c_str or not c_str:
        if (df[col] == "").all():
            continue
    cols_to_keep.append(col)

print(cols_to_keep)
