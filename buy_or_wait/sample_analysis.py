import pandas as pd

from app import load_data, prepare_data, get_profile, clean_user_events


data = prepare_data(load_data())

samples = pd.read_csv("data/sample_requests.csv")


for _, request in samples.iterrows():

    request_id = str(request["request_id"])
    user_id = str(request["user_id"])

    profile = get_profile(data, user_id)

    events = clean_user_events(
        data,
        user_id,
        request_id
    )

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events["settlement_date"] = pd.to_datetime(
        events["settlement_date"],
        errors="coerce"
    )

    request_date = pd.Timestamp(
        request["request_date"]
    )

    print("\n" + "=" * 75)
    print(request_id)

    print(
        "Expected:",
        request["affordability_status"],
        "|",
        request["recommended_payment_method"],
        "| safe amount:",
        request["amount_safe_to_pay"]
    )

    print(
        "Balance:",
        profile["current_available_balance"],
        "| Minimum:",
        profile["minimum_balance_to_keep"],
        "| Currency:",
        profile["home_currency"]
    )

    print("\nFuture explicit events:")

    future = events[
        events["event_date"] >= request_date
    ].sort_values("event_date")

    if future.empty:
        print("NONE")
    else:
        print(
            future[
                [
                    "event_id",
                    "event_type",
                    "category",
                    "direction",
                    "amount",
                    "event_date",
                    "settlement_date",
                    "status",
                    "flexibility"
                ]
            ].head(15).to_string(index=False)
        )

    print("\nMessages:")

    messages = data["messages"]

    relevant = messages[
        (
            messages["user_id"].astype(str) == user_id
        )
        |
        (
            messages["request_id"].astype(str)
            == request_id
        )
    ]

    if relevant.empty:
        print("NONE")
    else:
        for _, msg in relevant.iterrows():
            print("-", msg["message_text"])