import pandas as pd

sample = pd.read_csv("data/sample_requests.csv")
output = pd.read_csv("data/output.csv")

columns = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
]

merged = sample[columns].merge(
    output[columns],
    on="request_id",
    how="left",
    suffixes=("_expected", "_actual")
)

print("\n===== SAMPLE COMPARISON =====")

for _, row in merged.iterrows():

    print(f"\n{row['request_id']}")

    for column in columns[1:]:

        expected = row[f"{column}_expected"]
        actual = row[f"{column}_actual"]

        # Treat NaN and empty strings as equivalent for this comparison.
        expected_text = "" if pd.isna(expected) else str(expected)
        actual_text = "" if pd.isna(actual) else str(actual)

        if expected_text == actual_text:
            print(f"  {column}: ✅ MATCH")

        else:
            print(f"  {column}: ❌ DIFFER")
            print(f"      Expected: {expected_text}")
            print(f"      Actual:   {actual_text}")


print("\n===== SUMMARY =====")

total_values = 0
matching_values = 0

for column in columns[1:]:

    expected = merged[f"{column}_expected"].fillna("")
    actual = merged[f"{column}_actual"].fillna("")

    matches = expected.astype(str) == actual.astype(str)

    total_values += len(matches)
    matching_values += int(matches.sum())

    print(
        f"{column}: "
        f"{int(matches.sum())}/{len(matches)} match"
    )

print(
    f"\nTOTAL FIELD MATCH: "
    f"{matching_values}/{total_values}"
)
print(
    f"MATCH RATE: "
    f"{matching_values / total_values * 100:.2f}%"
)