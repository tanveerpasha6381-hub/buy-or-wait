import pandas as pd

file_path = "data/exchange_rates.csv"

df = pd.read_csv(file_path)

print("\n===== ALL COLUMNS =====\n")

for number, column in enumerate(df.columns, start=1):
    print(f"{number}. {column}")

print("\n===== TOTAL COLUMNS =====")
print(len(df.columns))

print("\n===== FIRST 20 ROWS =====")
print(df.head(20).to_string())

print("\n===== DATA TYPES =====\n")
print(df.dtypes)