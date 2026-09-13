import pandas as pd

from app import (
    load_data,
    prepare_data,
    clean_user_events,
    get_profile,
)


data = load_data()
data = prepare_data(data)

samples = pd.read_csv(
    "data/sample_requests.csv"
)


for _, request in samples.head(5).iterrows():

    request_id = str(request["request_id"])
    user_id = str(request["user_id"])

    request_date = pd.Timestamp(
        request["request_date"]
    )

    print("\n" + "=" * 70)
    print(request_id, "|", user_id)
    print("=" * 70)

    print("Request date:", request_date)
    print("Requested amount:", request["requested_amount"])
    print("Deadline:", request["desired_completion_date"])

    profile = get_profile(
        data,
        user_id
    )

    print("\nPROFILE")
    print(
        "Balance:",
        profile["current_available_balance"]
    )
    print(
        "Minimum:",
        profile["minimum_balance_to_keep"]
    )
    print(
        "Currency:",
        profile["home_currency"]
    )

    events = clean_user_events(
        data,
        user_id,
        request_id
    )

    if events.empty:
        print("\nNo events")
        continue

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events["settlement_date"] = pd.to_datetime(
        events["settlement_date"],
        errors="coerce"
    )

    print("\nEVENTS BEFORE REQUEST")

    before = events[
        events["event_date"] < request_date
    ].sort_values("event_date")

    print(
        before[
            [
                "event_id",
                "event_type",
                "category",
                "direction",
                "amount",
                "event_date",
                "settlement_date",
                "status",
                "flexibility",
            ]
        ].tail(20).to_string(index=False)
    )

    print("\nEVENTS ON/AFTER REQUEST")

    after = events[
        events["event_date"] >= request_date
    ].sort_values("event_date")

    if after.empty:
        print("NONE")

    else:
        print(
            after[
                [
                    "event_id",
                    "event_type",
                    "category",
                    "direction",
                    "amount",
                    "event_date",
                    "settlement_date",
                    "status",
                    "flexibility",
                ]
            ].head(30).to_string(index=False)
        )

    print("\nMESSAGES")

    messages = data["messages"]

    user_messages = messages[
        (
            messages["user_id"].astype(str)
            == user_id
        )
        |
        (
            messages["request_id"].astype(str)
            == request_id
        )
    ]

    if user_messages.empty:
        print("NONE")
    else:
        print(
            user_messages[
                [
                    "message_id",
                    "request_id",
                    "related_event_id",
                    "source_type",
                    "message_text",
                ]
            ].to_string(index=False)
        )