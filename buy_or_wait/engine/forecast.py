import pandas as pd
from pathlib import Path


# Project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Data folder
DATA_DIR = BASE_DIR / "data"


def load_csv_files():
    """Load the required CSV files."""
    return {
        "requests": pd.read_csv(DATA_DIR / "requests.csv"),
        "profiles": pd.read_csv(DATA_DIR / "financial_profiles.csv"),
        "events": pd.read_csv(DATA_DIR / "financial_events.csv"),
    }


def prepare_events(events):
    """Clean financial events."""
    events = events.copy()

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events["settlement_date"] = pd.to_datetime(
        events["settlement_date"],
        errors="coerce"
    )

    events["amount"] = pd.to_numeric(
        events["amount"],
        errors="coerce"
    )

    # Only cash movements affect the balance.
    events = events[
        events["direction"].isin(["debit", "credit"])
    ].copy()

    # Ignore events that are not confirmed cash movements.
    events = events[
        ~events["status"].isin(
            ["pending", "failed", "cancelled", "unrealized"]
        )
    ].copy()

    # Missing amounts will be handled later.
    events = events[
        events["amount"].notna()
    ].copy()

    return events


def get_user_profile(profiles, user_id):
    """Return the profile for one user."""
    row = profiles[
        profiles["user_id"] == user_id
    ]

    if row.empty:
        raise ValueError(
            f"Profile not found for user: {user_id}"
        )

    return row.iloc[0]


def get_user_events(events, user_id):
    """Return only this user's events."""
    return events[
        events["user_id"] == user_id
    ].copy()


def forecast_90_days(profile, user_events, request_date):
    """Create a simple 90-day balance forecast."""

    request_date = pd.Timestamp(request_date)
    end_date = request_date + pd.Timedelta(days=90)

    balance = float(
        profile["current_available_balance"]
    )

    minimum_balance = float(
        profile["minimum_balance_to_keep"]
    )

    # Filter events for the 90-day window.
    forecast_events = user_events[
        (user_events["event_date"] >= request_date)
        &
        (user_events["event_date"] <= end_date)
    ].copy()

    forecast_events = forecast_events.sort_values(
        "event_date"
    )

    forecast = []

    # Starting balance.
    forecast.append({
        "date": request_date.date(),
        "event": "starting_balance",
        "change": 0.0,
        "balance": balance,
        "safe": balance >= minimum_balance
    })

    # Apply financial events.
    for _, event in forecast_events.iterrows():

        amount = float(event["amount"])

        if event["direction"] == "credit":
            change = amount

        elif event["direction"] == "debit":
            change = -amount

        else:
            continue

        balance += change

        forecast.append({
            "date": event["event_date"].date(),
            "event": event["description"],
            "change": change,
            "balance": balance,
            "safe": balance >= minimum_balance
        })

    return pd.DataFrame(forecast)


if __name__ == "__main__":

    # 1. Load CSV files.
    data = load_csv_files()

    # 2. Prepare all events.
    events = prepare_events(
        data["events"]
    )

    # 3. Use the first request as a test.
    request = data["requests"].iloc[0]

    # 4. Get the corresponding user profile.
    profile = get_user_profile(
        data["profiles"],
        request["user_id"]
    )

    # 5. Get ONLY this user's events.
    user_events = get_user_events(
        events,
        request["user_id"]
    )

    # 6. Diagnostic information.
    print("\n===== REQUEST =====")
    print(request.to_string())

    print("\n===== USER PROFILE =====")
    print(profile.to_string())

    print("\n===== USER EVENT COUNT =====")
    print(len(user_events))

    print("\n===== USER EVENT DATE RANGE =====")
    print(
        "Earliest:",
        user_events["event_date"].min()
    )
    print(
        "Latest:",
        user_events["event_date"].max()
    )

    after_request = user_events[
        user_events["event_date"]
        >= pd.Timestamp(request["request_date"])
    ]

    print("\n===== EVENTS AFTER REQUEST DATE =====")
    print(len(after_request))

    print("\n===== FIRST 10 USER EVENTS =====")
    print(
        user_events[
            [
                "event_id",
                "event_type",
                "description",
                "amount",
                "event_date",
                "settlement_date",
                "status"
            ]
        ]
        .head(10)
        .to_string(index=False)
    )

    # 7. Run the 90-day forecast.
    forecast = forecast_90_days(
        profile,
        user_events,
        request["request_date"]
    )

    print("\n===== 90-DAY FORECAST =====")
    print(
        forecast.to_string(index=False)
    )

    print("\n===== LOWEST FORECAST BALANCE =====")
    print(
        forecast["balance"].min()
    )

    print("\n===== MINIMUM REQUIRED BALANCE =====")
    print(
        profile["minimum_balance_to_keep"]
    )