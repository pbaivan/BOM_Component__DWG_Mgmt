import pandas as pd
import io

# Mock data
df = pd.DataFrame({
    "PARENT": ["A", "B", ""],
    "Unnamed: 1": ["1", "", ""],  # Has some data
    "": ["", "", ""],            # Completely blank
    "Col_4": ["", "", ""]
})

cols_to_keep = []
final_cols = []
seen = set()

for i, col in enumerate(df.columns.tolist()):
    c_str = str(col).strip()
    is_unnamed = "Unnamed:" in c_str or not c_str
    
    if is_unnamed and (df[col] == "").all():
        continue
        
    if is_unnamed:
        c_str = f"Col_{i+1}"
        
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

print(final_cols)
print(df)
