import pandas as pd

from app import load_data, prepare_data, solve_request


# Load all data
data = load_data()
data = prepare_data(data)


# Load the official sample requests + expected answers
samples = pd.read_csv("data/sample_requests.csv")


print("\n========================================")
print("TESTING 25 OFFICIAL SAMPLE REQUESTS")
print("========================================\n")


results = []


for _, request in samples.iterrows():

    result = solve_request(
        request,
        data
    )

    results.append(result)


actual = pd.DataFrame(results)


# Compare important fields
fields = [
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
]


print("===== SUMMARY =====\n")


total = 0
matches = 0


for field in fields:

    field_matches = 0

    for _, sample in samples.iterrows():

        request_id = sample["request_id"]

        expected = sample[field]

        actual_row = actual[
            actual["request_id"] == request_id
        ].iloc[0]

        actual_value = actual_row[field]

        # Treat NaN and empty values as equivalent
        expected_text = (
            ""
            if pd.isna(expected)
            else str(expected).strip()
        )

        actual_text = (
            ""
            if pd.isna(actual_value)
            else str(actual_value).strip()
        )

        # Numeric comparison for amount
        if field == "amount_safe_to_pay":

            try:
                same = (
                    abs(
                        float(expected)
                        - float(actual_value)
                    )
                    < 0.01
                )
            except:
                same = False

        else:
            same = (
                expected_text
                == actual_text
            )

        total += 1

        if same:
            field_matches += 1
            matches += 1

    print(
        f"{field}: "
        f"{field_matches}/25 match"
    )


print(
    f"\nTOTAL MATCH: "
    f"{matches}/{total}"
)

print(
    f"MATCH RATE: "
    f"{matches / total * 100:.2f}%"
)


# Show detailed differences
print("\n========================================")
print("DETAILED DIFFERENCES")
print("========================================")


for _, sample in samples.iterrows():

    request_id = sample["request_id"]

    actual_row = actual[
        actual["request_id"] == request_id
    ].iloc[0]

    differences = []

    for field in fields:

        expected = sample[field]
        actual_value = actual_row[field]

        expected_text = (
            ""
            if pd.isna(expected)
            else str(expected).strip()
        )

        actual_text = (
            ""
            if pd.isna(actual_value)
            else str(actual_value).strip()
        )

        if field == "amount_safe_to_pay":

            try:
                same = (
                    abs(
                        float(expected)
                        - float(actual_value)
                    )
                    < 0.01
                )
            except:
                same = False

        else:
            same = (
                expected_text
                == actual_text
            )

        if not same:

            differences.append(
                (
                    field,
                    expected_text,
                    actual_text
                )
            )

    if differences:

        print(f"\n{request_id}")

        for field, expected, actual_value in differences:

            print(f"  {field}")
            print(f"    Expected: {expected}")
            print(f"    Actual:   {actual_value}")