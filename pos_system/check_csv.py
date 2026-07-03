import pandas as pd
from pathlib import Path

csv_path = sorted(Path("downloads").glob("*.csv"))[-1]
print(f"ファイル: {csv_path}")

df = pd.read_csv(csv_path, encoding="shift_jis")
print(f"カラム数: {len(df.columns)}")
print(f"行数: {len(df)}")
print("カラム名:")
for i, c in enumerate(df.columns):
    print(f"  {i+1:2d}: {c}")
