from pathlib import Path
from datetime import timedelta
from itertools import combinations
import re

import pandas as pd
from flask import Flask, render_template, request


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

REQUESTS_FILE = DATA_DIR / "requests.csv"
PROFILES_FILE = DATA_DIR / "financial_profiles.csv"
EVENTS_FILE = DATA_DIR / "financial_events.csv"
PAYMENT_OPTIONS_FILE = DATA_DIR / "request_payment_options.csv"
MESSAGES_FILE = DATA_DIR / "messages.csv"
IMAGES_FILE = DATA_DIR / "images.csv"
RATES_FILE = DATA_DIR / "exchange_rates.csv"
OUTPUT_FILE = DATA_DIR / "output.csv"


# ============================================================
# LOAD DATA
# ============================================================

def load_data():
    return {
        "requests": pd.read_csv(REQUESTS_FILE),
        "profiles": pd.read_csv(PROFILES_FILE),
        "events": pd.read_csv(EVENTS_FILE),
        "options": pd.read_csv(PAYMENT_OPTIONS_FILE),
        "messages": pd.read_csv(MESSAGES_FILE),
        "images": pd.read_csv(IMAGES_FILE),
        "rates": pd.read_csv(RATES_FILE),
    }


# ============================================================
# DATA PREPARATION
# ============================================================

def prepare_data(data):

    requests_df = data["requests"].copy()
    profiles = data["profiles"].copy()
    events = data["events"].copy()
    options = data["options"].copy()
    messages = data["messages"].copy()
    images = data["images"].copy()
    rates = data["rates"].copy()

    requests_df["request_date"] = pd.to_datetime(
        requests_df["request_date"],
        errors="coerce"
    )

    requests_df["desired_completion_date"] = pd.to_datetime(
        requests_df["desired_completion_date"],
        errors="coerce"
    )

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events["settlement_date"] = pd.to_datetime(
        events["settlement_date"],
        errors="coerce"
    )

    options["first_payment_date"] = pd.to_datetime(
        options["first_payment_date"],
        errors="coerce"
    )

    rates["rate_date"] = pd.to_datetime(
        rates["rate_date"],
        errors="coerce"
    )

    for column in [
        "amount",
        "minimum_allowed_amount"
    ]:
        if column in events.columns:
            events[column] = pd.to_numeric(
                events[column],
                errors="coerce"
            )

    for column in [
        "current_available_balance",
        "minimum_balance_to_keep",
        "max_installment_months"
    ]:
        if column in profiles.columns:
            profiles[column] = pd.to_numeric(
                profiles[column],
                errors="coerce"
            )

    for column in [
        "payment_amount",
        "number_of_payments",
        "payment_frequency_days",
        "financing_fee",
        "total_payable_amount"
    ]:
        if column in options.columns:
            options[column] = pd.to_numeric(
                options[column],
                errors="coerce"
            )

    if "rate" in rates.columns:
        rates["rate"] = pd.to_numeric(
            rates["rate"],
            errors="coerce"
        )

    data["requests"] = requests_df
    data["profiles"] = profiles
    data["events"] = events
    data["options"] = options
    data["messages"] = messages
    data["images"] = images
    data["rates"] = rates

    return data


# ============================================================
# BASIC HELPERS
# ============================================================

def split_values(value):

    if value is None or pd.isna(value):
        return set()

    return {
        item.strip().lower()
        for item in str(value).split("|")
        if item.strip()
    }


def money(value):

    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def parse_amounts_from_text(text):

    if text is None or pd.isna(text):
        return []

    text = str(text)

    results = []

    pattern = (
        r"(?<![\w])"
        r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
        r"(?![\w])"
    )

    for match in re.findall(pattern, text):

        try:
            results.append(
                float(match.replace(",", ""))
            )
        except ValueError:
            pass

    return results


# ============================================================
# EXCHANGE RATES
# ============================================================

def get_rate(
    rates,
    rate_date,
    from_currency,
    to_currency
):

    if rate_date is None or pd.isna(rate_date):
        return None

    from_currency = str(from_currency).upper()
    to_currency = str(to_currency).upper()

    if from_currency == to_currency:
        return 1.0

    target_date = pd.Timestamp(rate_date)

    exact = rates[
        (rates["rate_date"] == target_date)
        &
        (
            rates["from_currency"]
            .astype(str)
            .str.upper()
            == from_currency
        )
        &
        (
            rates["to_currency"]
            .astype(str)
            .str.upper()
            == to_currency
        )
    ]

    if not exact.empty:
        return float(
            exact.iloc[0]["rate"]
        )

    reverse = rates[
        (rates["rate_date"] == target_date)
        &
        (
            rates["from_currency"]
            .astype(str)
            .str.upper()
            == to_currency
        )
        &
        (
            rates["to_currency"]
            .astype(str)
            .str.upper()
            == from_currency
        )
    ]

    if not reverse.empty:

        value = float(
            reverse.iloc[0]["rate"]
        )

        if value != 0:
            return 1.0 / value

    candidates = rates[
        (
            rates["from_currency"]
            .astype(str)
            .str.upper()
            == from_currency
        )
        &
        (
            rates["to_currency"]
            .astype(str)
            .str.upper()
            == to_currency
        )
        &
        (
            rates["rate_date"]
            <= target_date
        )
    ].sort_values("rate_date")

    if not candidates.empty:
        return float(
            candidates.iloc[-1]["rate"]
        )

    reverse_candidates = rates[
        (
            rates["from_currency"]
            .astype(str)
            .str.upper()
            == to_currency
        )
        &
        (
            rates["to_currency"]
            .astype(str)
            .str.upper()
            == from_currency
        )
        &
        (
            rates["rate_date"]
            <= target_date
        )
    ].sort_values("rate_date")

    if not reverse_candidates.empty:

        value = float(
            reverse_candidates.iloc[-1]["rate"]
        )

        if value != 0:
            return 1.0 / value

    return None


def convert_amount(
    rates,
    amount,
    from_currency,
    to_currency,
    event_date
):

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None

    rate = get_rate(
        rates,
        event_date,
        from_currency,
        to_currency
    )

    if rate is None:
        return None

    return amount * rate


# ============================================================
# USER DATA
# ============================================================

def get_profile(data, user_id):

    rows = data["profiles"][
        data["profiles"]["user_id"]
        .astype(str)
        == str(user_id)
    ]

    if rows.empty:
        return None

    return rows.iloc[0]


def get_user_events(data, user_id):

    return data["events"][
        data["events"]["user_id"]
        .astype(str)
        == str(user_id)
    ].copy()


def get_user_messages(
    data,
    user_id,
    request_id
):

    messages = data["messages"]

    return messages[
        (
            messages["user_id"]
            .astype(str)
            == str(user_id)
        )
        |
        (
            messages["request_id"]
            .astype(str)
            == str(request_id)
        )
    ].copy()


# ============================================================
# CLEAN EVENTS
# ============================================================

def clean_user_events(
    data,
    user_id,
    request_id
):

    events = get_user_events(
        data,
        user_id
    ).copy()

    if events.empty:
        return events

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

    bad_statuses = {
        "failed",
        "cancelled",
        "unrealized"
    }

    events = events[
        ~events["status"]
        .astype(str)
        .str.lower()
        .isin(bad_statuses)
    ].copy()

    pending_credit = (
        events["status"]
        .astype(str)
        .str.lower()
        .eq("pending")
        &
        events["direction"]
        .astype(str)
        .str.lower()
        .eq("credit")
    )

    events = events[
        ~pending_credit
    ].copy()

    events = events[
        events["direction"]
        .astype(str)
        .str.lower()
        .isin([
            "credit",
            "debit"
        ])
    ].copy()

    return events


# ============================================================
# MESSAGE OVERRIDES
# ============================================================

def build_message_overrides(
    data,
    user_id,
    request_id
):

    messages = get_user_messages(
        data,
        user_id,
        request_id
    )

    overrides = {}

    if messages.empty:
        return overrides

    for _, row in messages.iterrows():

        related_event_id = row.get(
            "related_event_id"
        )

        if pd.isna(related_event_id):
            continue

        amounts = parse_amounts_from_text(
            row.get(
                "message_text",
                ""
            )
        )

        if amounts:

            overrides[
                str(related_event_id)
            ] = amounts[0]

    return overrides


# ============================================================
# DUPLICATES
# ============================================================

def remove_simple_duplicates(events):

    if events.empty:
        return events

    columns = [
        "user_id",
        "event_type",
        "description",
        "category",
        "direction",
        "amount",
        "event_date",
        "settlement_date"
    ]

    columns = [
        column
        for column in columns
        if column in events.columns
    ]

    if not columns:
        return events

    return events.drop_duplicates(
        subset=columns
    ).copy()


# ============================================================
# NORMALIZE
# ============================================================

def normalize_events_to_home_currency(
    data,
    events,
    home_currency,
    message_overrides
):

    if events.empty:
        return events

    rates = data["rates"]

    rows = []

    for _, event in events.iterrows():

        event_id = str(
            event["event_id"]
        )

        amount = event["amount"]

        if pd.isna(amount):

            if event_id in message_overrides:
                amount = message_overrides[
                    event_id
                ]
            else:
                continue

        event_date = event[
            "settlement_date"
        ]

        if pd.isna(event_date):
            event_date = event["event_date"]

        if pd.isna(event_date):
            continue

        currency = str(
            event["currency"]
        ).upper()

        amount_home = convert_amount(
            rates,
            amount,
            currency,
            home_currency,
            event_date
        )

        if amount_home is None:

            if currency == str(
                home_currency
            ).upper():

                amount_home = float(
                    amount
                )

            else:
                continue

        row = event.copy()

        row["normalized_amount"] = (
            float(amount_home)
        )

        rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


# ============================================================
# CASH DATE
# ============================================================

def event_cash_date(row):

    settlement = row.get(
        "settlement_date"
    )

    if pd.notna(settlement):
        return pd.Timestamp(
            settlement
        )

    event_date = row.get(
        "event_date"
    )

    if pd.notna(event_date):
        return pd.Timestamp(
            event_date
        )

    return pd.NaT


# ============================================================
# RECURRING PATTERNS
# ============================================================

def detect_recurring_patterns(history):

    if history.empty:
        return []

    history = history.copy()

    history["cash_date"] = history.apply(
        event_cash_date,
        axis=1
    )

    history = history[
        history["cash_date"].notna()
    ].copy()

    if history.empty:
        return []

    group_columns = [
        "user_id",
        "event_type",
        "category",
        "direction",
        "description"
    ]

    for column in group_columns:

        if column not in history.columns:
            history[column] = ""

    patterns = []

    grouped = history.groupby(
        group_columns,
        dropna=False
    )

    for key, group in grouped:

        group = group.sort_values(
            "cash_date"
        )

        if len(group) < 2:
            continue

        dates = group[
            "cash_date"
        ].tolist()

        intervals = []

        for i in range(
            1,
            len(dates)
        ):

            gap = (
                dates[i]
                - dates[i - 1]
            ).days

            if gap > 0:
                intervals.append(gap)

        if not intervals:
            continue

        median_interval = float(
            pd.Series(intervals).median()
        )

        recognised = (
            5 <= median_interval <= 10
            or
            12 <= median_interval <= 18
            or
            25 <= median_interval <= 35
        )

        if not recognised:
            continue

        good = [
            abs(
                gap - median_interval
            ) <= 4
            for gap in intervals
        ]

        consistency = (
            sum(good)
            / len(good)
        )

        if consistency < 0.50:
            continue

        amounts = pd.to_numeric(
            group["normalized_amount"],
            errors="coerce"
        ).dropna()

        if amounts.empty:
            continue

        recent_amounts = amounts.tail(
            min(
                3,
                len(amounts)
            )
        )

        typical_amount = float(
            recent_amounts.median()
        )

        last_row = group.iloc[-1]

        event_id = str(
            last_row["event_id"]
        )

        minimum = last_row.get(
            "minimum_allowed_amount"
        )

        patterns.append({

            "user_id": key[0],

            "event_type": key[1],

            "category": key[2],

            "direction": key[3],

            "description": key[4],

            "interval_days": int(
                round(
                    median_interval
                )
            ),

            "amount": typical_amount,

            "last_date": group[
                "cash_date"
            ].max(),

            "confidence": round(
                consistency,
                2
            ),

            "event_id": event_id,

            "source_event_id": event_id,

            "flexibility": str(
                last_row.get(
                    "flexibility",
                    "fixed"
                )
            ),

            "minimum_allowed_amount": minimum,
        })

    return patterns


# ============================================================
# PROJECT PATTERNS
# ============================================================

def project_patterns(
    patterns,
    start_date,
    end_date
):

    projected = []

    start_date = pd.Timestamp(
        start_date
    )

    end_date = pd.Timestamp(
        end_date
    )

    for pattern in patterns:

        interval_days = int(
            pattern.get(
                "interval_days",
                0
            )
        )

        if interval_days <= 0:
            continue

        last_date = pd.Timestamp(
            pattern["last_date"]
        )

        next_date = (
            last_date
            + pd.Timedelta(
                days=interval_days
            )
        )

        while next_date <= end_date:

            if next_date >= start_date:

                projected.append({

                    "event_id": (
                        f"projection_"
                        f"{pattern['event_id']}_"
                        f"{next_date.strftime('%Y%m%d')}"
                    ),

                    "source_event_id": (
                        pattern["event_id"]
                    ),

                    "user_id": pattern[
                        "user_id"
                    ],

                    "event_type": pattern[
                        "event_type"
                    ],

                    "category": pattern[
                        "category"
                    ],

                    "direction": pattern[
                        "direction"
                    ],

                    "amount": float(
                        pattern["amount"]
                    ),

                    "event_date": next_date,

                    "settlement_date": next_date,

                    "description": pattern.get(
                        "description",
                        ""
                    ),

                    "flexibility": pattern.get(
                        "flexibility",
                        "fixed"
                    ),

                    "minimum_allowed_amount": (
                        pattern.get(
                            "minimum_allowed_amount",
                            0
                        )
                    ),

                    "source": (
                        "recurring_projection"
                    ),
                })

            next_date += pd.Timedelta(
                days=interval_days
            )

    if not projected:

        return pd.DataFrame(
            columns=[
                "event_id",
                "source_event_id",
                "user_id",
                "event_type",
                "category",
                "direction",
                "amount",
                "event_date",
                "settlement_date",
                "description",
                "flexibility",
                "minimum_allowed_amount",
                "source"
            ]
        )

    return pd.DataFrame(
        projected
    )


# ============================================================
# SPENDING CHANGES
# ============================================================

def get_user_allowed_changes(
    profile
):

    return {

        "reduce": split_values(
            profile.get(
                "expense_categories_user_is_willing_to_reduce"
            )
        ),

        "stop": split_values(
            profile.get(
                "expense_categories_user_is_willing_to_stop"
            )
        ),

        "protect": split_values(
            profile.get(
                "expense_categories_to_protect"
            )
        )
    }


def candidate_spending_changes(
    events,
    profile,
    patterns=None
):

    allowed = get_user_allowed_changes(
        profile
    )

    candidates = []

    if events.empty:
        return candidates

    if patterns:

        recurring_ids = {
            str(
                pattern["event_id"]
            )
            for pattern in patterns
        }

        source_events = events[
            events["event_id"]
            .astype(str)
            .isin(
                recurring_ids
            )
        ].copy()

        if source_events.empty:
            source_events = events.copy()

    else:

        source_events = events.copy()

    source_events = source_events[
        source_events[
            "flexibility"
        ]
        .astype(str)
        .str.lower()
        .isin([
            "reducible",
            "stoppable",
            "reducible_or_stoppable"
        ])
    ].copy()

    for _, event in source_events.iterrows():

        category = str(
            event.get(
                "category",
                ""
            )
        ).lower()

        event_id = str(
            event["event_id"]
        )

        amount = float(
            event["normalized_amount"]
        )

        flexibility = str(
            event.get(
                "flexibility",
                "fixed"
            )
        ).lower()

        if (
            category in allowed["stop"]
            and flexibility in [
                "stoppable",
                "reducible_or_stoppable"
            ]
        ):

            candidates.append({
                "type": "stop",
                "event_id": event_id,
                "amount": amount,
                "category": category
            })

        if (
            category in allowed["reduce"]
            and flexibility in [
                "reducible",
                "reducible_or_stoppable"
            ]
        ):

            minimum = event.get(
                "minimum_allowed_amount"
            )

            if pd.isna(minimum):
                minimum = amount * 0.5

            candidates.append({
                "type": "reduce",
                "event_id": event_id,
                "amount": amount,
                "minimum": min(
                    float(minimum),
                    amount
                ),
                "category": category
            })

    unique = {}

    for candidate in candidates:

        key = (
            candidate["type"],
            candidate["event_id"]
        )

        unique[key] = candidate

    return list(
        unique.values()
    )


def apply_spending_changes(
    future_events,
    changes
):

    if (
        future_events.empty
        or not changes
    ):
        return future_events.copy()

    rows = []

    stop_ids = {
        str(
            change["event_id"]
        )
        for change in changes
        if change["type"] == "stop"
    }

    reduce_map = {
        str(
            change["event_id"]
        ): change
        for change in changes
        if change["type"] == "reduce"
    }

    for _, event in future_events.iterrows():

        row = event.copy()

        event_id = str(
            event.get(
                "event_id",
                ""
            )
        )

        source_id = str(
            event.get(
                "source_event_id",
                event_id
            )
        )

        ids = {
            event_id,
            source_id
        }

        if ids.intersection(
            stop_ids
        ):
            continue

        reduction = None

        for change_id, change in reduce_map.items():

            if change_id in ids:
                reduction = change
                break

        if reduction is not None:

            row["amount"] = min(
                float(row["amount"]),
                float(
                    reduction["minimum"]
                )
            )

        rows.append(row)

    if not rows:

        return pd.DataFrame(
            columns=future_events.columns
        )

    return pd.DataFrame(rows)


# ============================================================
# BALANCE SIMULATION
# ============================================================

def simulate_balance(
    starting_balance,
    minimum_balance,
    events,
    extra_payments=None
):

    extra_payments = (
        extra_payments
        or []
    )

    timeline = []

    if (
        events is not None
        and not events.empty
    ):

        for _, event in events.iterrows():

            date = event.get(
                "event_date"
            )

            if pd.isna(date):
                continue

            direction = str(
                event.get(
                    "direction",
                    ""
                )
            ).lower()

            try:
                amount = float(
                    event["amount"]
                )
            except (
                TypeError,
                ValueError
            ):
                continue

            if direction == "credit":
                change = amount

            elif direction == "debit":
                change = -amount

            else:
                continue

            timeline.append({
                "date": pd.Timestamp(date),
                "change": change,
                "description": event.get(
                    "description",
                    "financial_event"
                ),
                "payment": False
            })

    for payment in extra_payments:

        timeline.append({
            "date": pd.Timestamp(
                payment["date"]
            ),
            "change": -float(
                payment["amount"]
            ),
            "description": "request_payment",
            "payment": True
        })

    timeline.sort(
        key=lambda x: (
            x["date"],
            1 if x["payment"] else 0
        )
    )

    balance = float(
        starting_balance
    )

    rows = [{
        "date": None,
        "balance": balance,
        "safe": (
            balance >= minimum_balance
        ),
        "description": "starting_balance"
    }]

    if balance < minimum_balance:
        return (
            False,
            pd.DataFrame(rows)
        )

    for event in timeline:

        balance += event["change"]

        rows.append({
            "date": event["date"],
            "balance": balance,
            "safe": (
                balance >= minimum_balance
            ),
            "description": event[
                "description"
            ]
        })

        if balance < minimum_balance:

            return (
                False,
                pd.DataFrame(rows)
            )

    return (
        True,
        pd.DataFrame(rows)
    )


# ============================================================
# SAFE AMOUNT
# ============================================================

def amount_safe_today(
    current_balance,
    minimum_balance,
    future_events
):

    today_headroom = (
        float(current_balance)
        - float(minimum_balance)
    )

    if today_headroom <= 0:
        return 0.0

    if (
        future_events is None
        or future_events.empty
    ):
        return max(
            0.0,
            today_headroom
        )

    balance = float(
        current_balance
    )

    lowest_balance = balance

    events = future_events.copy()

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events = events[
        events["event_date"].notna()
    ].sort_values(
        "event_date"
    )

    for _, event in events.iterrows():

        amount = float(
            event["amount"]
        )

        direction = str(
            event["direction"]
        ).lower()

        if direction == "credit":
            balance += amount

        elif direction == "debit":
            balance -= amount

        lowest_balance = min(
            lowest_balance,
            balance
        )

    future_headroom = (
        lowest_balance
        - float(minimum_balance)
    )

    return max(
        0.0,
        min(
            today_headroom,
            future_headroom
        )
    )


# ============================================================
# PAYMENT METHODS
# ============================================================

def parse_profile_methods(
    profile
):

    return split_values(
        profile.get(
            "payment_methods_user_will_consider"
        )
    )


# ============================================================
# OPTION PLAN
# ============================================================

def option_plan(option):

    first_date = pd.Timestamp(
        option["first_payment_date"]
    )

    number = int(
        option["number_of_payments"]
    )

    frequency = option[
        "payment_frequency_days"
    ]

    amount = float(
        option["payment_amount"]
    )

    if number <= 0:
        return []

    payments = []

    for i in range(number):

        if pd.isna(frequency):

            date = first_date

        else:

            date = (
                first_date
                + timedelta(
                    days=int(
                        frequency * i
                    )
                )
            )

        payments.append({
            "date": date,
            "amount": amount
        })

    return payments


# ============================================================
# FORMAT PAYMENT PLAN
# ============================================================

def format_payment_plan(
    payments
):

    if not payments:
        return "none"

    payments = sorted(
        payments,
        key=lambda x: pd.Timestamp(
            x["date"]
        )
    )

    parts = []

    for payment in payments:

        date_text = pd.Timestamp(
            payment["date"]
        ).strftime(
            "%Y-%m-%d"
        )

        amount = float(
            payment["amount"]
        )

        # Preserve two decimal places when the supplied
        # payment amount actually has cents.
        if amount.is_integer():
            amount_text = str(
                int(amount)
            )
        else:
            amount_text = (
                f"{amount:.2f}"
                .rstrip("0")
                .rstrip(".")
            )

        parts.append(
            f"{date_text}:{amount_text}"
        )

    return "|".join(parts)


# ============================================================
# EARLIEST FULL PAYMENT
# ============================================================

def find_earliest_full_payment_date(
    request_date,
    desired_date,
    requested_amount,
    starting_balance,
    minimum_balance,
    future_events
):

    request_date = pd.Timestamp(
        request_date
    )

    # Search the entire 90-day forecast.
    # Deadline is checked separately.
    for day in range(0, 91):

        candidate = (
            request_date
            + timedelta(
                days=day
            )
        )

        payments = [{
            "date": candidate,
            "amount": requested_amount
        }]

        safe, _ = simulate_balance(
            starting_balance,
            minimum_balance,
            future_events,
            payments
        )

        if safe:
            return candidate

    return None


# ============================================================
# CANDIDATE HELPERS
# ============================================================

def changes_are_compatible(
    changes
):

    ids = [
        str(
            change["event_id"]
        )
        for change in changes
    ]

    return len(ids) == len(
        set(ids)
    )


def add_candidate(
    candidates,
    method,
    payments,
    total_paid,
    spending_changes,
    option_id=""
):

    if not payments:
        return

    candidates.append({
        "method": method,
        "payments": payments,
        "total_paid": float(
            total_paid
        ),
        "spending_changes": (
            spending_changes
        ),
        "option_id": str(
            option_id
        ) if option_id else ""
    })


# ============================================================
# SOLVE ONE REQUEST
# ============================================================

def solve_request(
    request_row,
    data
):

    request_id = str(
        request_row["request_id"]
    )

    user_id = str(
        request_row["user_id"]
    )

    request_date = pd.Timestamp(
        request_row["request_date"]
    )

    desired_date = pd.Timestamp(
        request_row[
            "desired_completion_date"
        ]
    )

    requested_amount = float(
        request_row[
            "requested_amount"
        ]
    )

    profile = get_profile(
        data,
        user_id
    )

    if profile is None:

        return fallback_result(
            request_row,
            "Financial profile not found."
        )

    home_currency = str(
        profile["home_currency"]
    ).upper()

    current_balance = float(
        profile[
            "current_available_balance"
        ]
    )

    minimum_balance = float(
        profile[
            "minimum_balance_to_keep"
        ]
    )

    methods = parse_profile_methods(
        profile
    )

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------

    events = clean_user_events(
        data,
        user_id,
        request_id
    )

    events = remove_simple_duplicates(
        events
    )

    overrides = build_message_overrides(
        data,
        user_id,
        request_id
    )

    events = normalize_events_to_home_currency(
        data,
        events,
        home_currency,
        overrides
    )

    if events.empty:

        events = pd.DataFrame(
            columns=[
                "event_id",
                "user_id",
                "event_type",
                "description",
                "category",
                "direction",
                "normalized_amount",
                "event_date",
                "settlement_date",
                "flexibility",
                "minimum_allowed_amount"
            ]
        )

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events["settlement_date"] = pd.to_datetime(
        events["settlement_date"],
        errors="coerce"
    )

    events["cash_date"] = events.apply(
        event_cash_date,
        axis=1
    )

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    history = events[
        events["cash_date"]
        < request_date
    ].copy()

    patterns = detect_recurring_patterns(
        history
    )

    future_end = (
        request_date
        + timedelta(days=90)
    )

    projected = project_patterns(
        patterns,
        request_date,
        future_end
    )

    # --------------------------------------------------------
    # EXPLICIT FUTURE EVENTS
    # --------------------------------------------------------

    explicit_future = events[
        (
            events["cash_date"]
            >= request_date
        )
        &
        (
            events["cash_date"]
            <= future_end
        )
    ].copy()

    if not explicit_future.empty:

        explicit_future = explicit_future[
            [
                "event_id",
                "user_id",
                "event_type",
                "category",
                "direction",
                "normalized_amount",
                "cash_date",
                "description",
                "flexibility",
                "minimum_allowed_amount"
            ]
        ].rename(
            columns={
                "normalized_amount": "amount",
                "cash_date": "event_date"
            }
        )

        explicit_future[
            "source_event_id"
        ] = explicit_future[
            "event_id"
        ].astype(str)

        explicit_future[
            "settlement_date"
        ] = explicit_future[
            "event_date"
        ]

        explicit_future[
            "source"
        ] = "explicit_event"

    else:

        explicit_future = pd.DataFrame(
            columns=[
                "event_id",
                "source_event_id",
                "user_id",
                "event_type",
                "category",
                "direction",
                "amount",
                "event_date",
                "settlement_date",
                "description",
                "flexibility",
                "minimum_allowed_amount",
                "source"
            ]
        )

    # --------------------------------------------------------
    # COMBINE
    # --------------------------------------------------------

    parts = []

    if not explicit_future.empty:
        parts.append(
            explicit_future
        )

    if not projected.empty:
        parts.append(
            projected
        )

    if parts:

        future_events = pd.concat(
            parts,
            ignore_index=True
        )

    else:

        future_events = pd.DataFrame(
            columns=[
                "event_id",
                "source_event_id",
                "user_id",
                "event_type",
                "category",
                "direction",
                "amount",
                "event_date",
                "settlement_date",
                "description",
                "flexibility",
                "minimum_allowed_amount",
                "source"
            ]
        )

    future_events["event_date"] = pd.to_datetime(
        future_events["event_date"],
        errors="coerce"
    )

    future_events = future_events[
        future_events["event_date"].notna()
    ].sort_values(
        "event_date"
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # SAFE AMOUNT
    # --------------------------------------------------------

    safe_today = amount_safe_today(
        current_balance,
        minimum_balance,
        future_events
    )

    safe_today = max(
        0.0,
        min(
            safe_today,
            requested_amount
        )
    )

    # --------------------------------------------------------
    # EARLIEST FULL PAYMENT
    # --------------------------------------------------------

    earliest_full = (
        find_earliest_full_payment_date(
            request_date,
            desired_date,
            requested_amount,
            current_balance,
            minimum_balance,
            future_events
        )
    )

    # --------------------------------------------------------
    # PAYMENT OPTIONS
    # --------------------------------------------------------

    options = data["options"]

    request_options = options[
        options["request_id"]
        .astype(str)
        == request_id
    ].copy()

    candidates = []

    # ========================================================
    # FULL PAYMENT
    # ========================================================

    if "full_payment" in methods:

        payments = [{
            "date": request_date,
            "amount": requested_amount
        }]

        safe, _ = simulate_balance(
            current_balance,
            minimum_balance,
            future_events,
            payments
        )

        if (
            safe
            and request_date <= desired_date
        ):

            add_candidate(
                candidates,
                "full_payment",
                payments,
                requested_amount,
                [],
                ""
            )

    # ========================================================
    # PARTIAL PAYMENT
    # ========================================================

    allows_partial = (
        str(
            request_row[
                "allows_partial_payment"
            ]
        ).lower()
        in {
            "true",
            "1",
            "yes"
        }
    )

    if (
        allows_partial
        and "partial_payment" in methods
        and safe_today > 0
        and safe_today < requested_amount
        and earliest_full is not None
        and earliest_full <= desired_date
    ):

        payments = [
            {
                "date": request_date,
                "amount": safe_today
            },
            {
                "date": earliest_full,
                "amount": (
                    requested_amount
                    - safe_today
                )
            }
        ]

        safe, _ = simulate_balance(
            current_balance,
            minimum_balance,
            future_events,
            payments
        )

        if safe:

            add_candidate(
                candidates,
                "partial_payment",
                payments,
                requested_amount,
                [],
                ""
            )

    # ========================================================
    # INSTALLMENTS
    # ========================================================

    if "installments" in methods:

        for _, option in request_options.iterrows():

            if (
                str(
                    option[
                        "payment_method"
                    ]
                ).lower()
                != "installments"
            ):
                continue

            payments = option_plan(
                option
            )

            if not payments:
                continue

            last_date = max(
                pd.Timestamp(
                    payment["date"]
                )
                for payment in payments
            )

            if last_date > desired_date:
                continue

            max_months = profile.get(
                "max_installment_months"
            )

            if (
                pd.notna(max_months)
                and
                len(payments)
                > int(max_months)
            ):
                continue

            safe, _ = simulate_balance(
                current_balance,
                minimum_balance,
                future_events,
                payments
            )

            if safe:

                total_payable = float(
                    option.get(
                        "total_payable_amount",
                        sum(
                            payment["amount"]
                            for payment in payments
                        )
                    )
                )

                add_candidate(
                    candidates,
                    "installments",
                    payments,
                    total_payable,
                    [],
                    option[
                        "payment_option_id"
                    ]
                )

    # ========================================================
    # SPENDING CHANGES
    # ========================================================

    change_candidates = (
        candidate_spending_changes(
            events,
            profile,
            patterns
        )
    )

    change_sets = [[]]

    for size in range(
        1,
        min(
            3,
            len(change_candidates)
        ) + 1
    ):

        for combo in combinations(
            change_candidates,
            size
        ):

            combo = list(combo)

            if changes_are_compatible(
                combo
            ):
                change_sets.append(
                    combo
                )

    for changes in change_sets:

        if not changes:
            continue

        modified_future = (
            apply_spending_changes(
                future_events,
                changes
            )
        )

        # ----------------------------------------------------
        # Full payment with changes
        # ----------------------------------------------------

        if "full_payment" in methods:

            payments = [{
                "date": request_date,
                "amount": requested_amount
            }]

            safe, _ = simulate_balance(
                current_balance,
                minimum_balance,
                modified_future,
                payments
            )

            if (
                safe
                and request_date <= desired_date
            ):

                add_candidate(
                    candidates,
                    "full_payment",
                    payments,
                    requested_amount,
                    changes,
                    ""
                )

        # ----------------------------------------------------
        # Installments with changes
        # ----------------------------------------------------

        if "installments" in methods:

            for _, option in request_options.iterrows():

                if (
                    str(
                        option[
                            "payment_method"
                        ]
                    ).lower()
                    != "installments"
                ):
                    continue

                payments = option_plan(
                    option
                )

                if not payments:
                    continue

                last_date = max(
                    pd.Timestamp(
                        payment["date"]
                    )
                    for payment in payments
                )

                if last_date > desired_date:
                    continue

                safe, _ = simulate_balance(
                    current_balance,
                    minimum_balance,
                    modified_future,
                    payments
                )

                if safe:

                    total_payable = float(
                        option.get(
                            "total_payable_amount",
                            sum(
                                payment["amount"]
                                for payment in payments
                            )
                        )
                    )

                    add_candidate(
                        candidates,
                        "installments",
                        payments,
                        total_payable,
                        changes,
                        option[
                            "payment_option_id"
                        ]
                    )

    # ========================================================
    # WAIT
    # ========================================================

    if (
        earliest_full is not None
        and earliest_full > request_date
        and earliest_full <= desired_date
        and "full_payment" in methods
    ):

        add_candidate(
            candidates,
            "wait",
            [{
                "date": earliest_full,
                "amount": requested_amount
            }],
            requested_amount,
            [],
            ""
        )

    # ========================================================
    # NO CANDIDATE
    # ========================================================

    if not candidates:

        if (
            earliest_full is not None
            and earliest_full <= desired_date
            and "full_payment" in methods
        ):

            status = "affordable_later"
            method = "wait"

            plan = format_payment_plan([
                {
                    "date": earliest_full,
                    "amount": requested_amount
                }
            ])

        else:

            status = "not_affordable"
            method = "not_recommended"
            plan = "none"

        explanation = (
            f"Current balance is "
            f"{current_balance:.2f} "
            f"{home_currency}; minimum balance "
            f"to keep is "
            f"{minimum_balance:.2f} "
            f"{home_currency}. "
            f"Maximum safe amount today is "
            f"{safe_today:.2f} "
            f"{home_currency}."
        )

        return {
            "request_id": request_id,
            "amount_safe_to_pay": money(
                safe_today
            ),
            "affordability_status": status,
            "recommended_payment_method": method,
            "payment_plan": plan,
            "earliest_date_for_full_payment": (
                earliest_full.strftime(
                    "%Y-%m-%d"
                )
                if earliest_full is not None
                else ""
            ),
            "spending_changes_needed": "none",
            "decision_explanation": explanation
        }

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique = {}

    for candidate in candidates:

        payment_key = tuple(
            (
                pd.Timestamp(
                    payment["date"]
                ).strftime(
                    "%Y-%m-%d"
                ),
                round(
                    float(
                        payment["amount"]
                    ),
                    2
                )
            )
            for payment in candidate[
                "payments"
            ]
        )

        changes_key = tuple(
            sorted(
                (
                    change["type"],
                    str(
                        change["event_id"]
                    )
                )
                for change in candidate[
                    "spending_changes"
                ]
            )
        )

        key = (
            candidate["method"],
            candidate["option_id"],
            payment_key,
            changes_key
        )

        unique[key] = candidate

    candidates = list(
        unique.values()
    )

    # ========================================================
    # RANK
    # ========================================================

    def rank(candidate):

        payments = candidate[
            "payments"
        ]

        last_date = max(
            pd.Timestamp(
                payment["date"]
            )
            for payment in payments
        )

        start_date = min(
            pd.Timestamp(
                payment["date"]
            )
            for payment in payments
        )

        completes_by_deadline = (
            last_date <= desired_date
        )

        no_changes = (
            len(
                candidate[
                    "spending_changes"
                ]
            ) == 0
        )

        total_paid = float(
            candidate[
                "total_paid"
            ]
        )

        count = len(
            payments
        )

        option_id = (
            candidate[
                "option_id"
            ]
            or "zzzzzz"
        )

        return (
            not completes_by_deadline,
            not no_changes,
            total_paid,
            start_date,
            count,
            option_id
        )

    candidates.sort(
        key=rank
    )

    best = candidates[0]

    # ========================================================
    # STATUS
    # ========================================================

    if best["method"] == "full_payment":

        status = "affordable_now"

    elif best["method"] in {
        "partial_payment",
        "installments"
    }:

        status = "affordable_with_plan"

    elif best["method"] == "wait":

        status = "affordable_later"

    else:

        status = "not_affordable"

    # ========================================================
    # SPENDING CHANGES TEXT
    # ========================================================

    change_strings = []

    for change in best[
        "spending_changes"
    ]:

        if change["type"] == "stop":

            change_strings.append(
                f"stop:{change['event_id']}"
            )

        elif change["type"] == "reduce":

            change_strings.append(
                f"reduce_to:"
                f"{change['event_id']}:"
                f"{money(change['minimum']):.2f}"
            )

    changes_text = (
        "|".join(change_strings)
        if change_strings
        else "none"
    )

    # ========================================================
    # PAYMENT PLAN
    # ========================================================

    plan_text = format_payment_plan(
        best["payments"]
    )

    # ========================================================
    # EXPLANATION
    # ========================================================

    explanation = (
        f"Current balance: "
        f"{current_balance:.2f} "
        f"{home_currency}. "
        f"Required minimum: "
        f"{minimum_balance:.2f} "
        f"{home_currency}. "
        f"Safe amount today: "
        f"{safe_today:.2f} "
        f"{home_currency}. "
        f"Recommended method: "
        f"{best['method']}."
    )

    if earliest_full is not None:

        explanation += (
            f" Full payment is first forecast "
            f"safe on "
            f"{earliest_full.strftime('%Y-%m-%d')}."
        )

    if best[
        "spending_changes"
    ]:

        explanation += (
            " Allowed spending changes "
            "are included in the plan."
        )

    return {
        "request_id": request_id,

        "amount_safe_to_pay": money(
            safe_today
        ),

        "affordability_status": status,

        "recommended_payment_method": (
            best["method"]
        ),

        "payment_plan": plan_text,

        "earliest_date_for_full_payment": (
            earliest_full.strftime(
                "%Y-%m-%d"
            )
            if earliest_full is not None
            else ""
        ),

        "spending_changes_needed": (
            changes_text
        ),

        "decision_explanation": (
            explanation
        )
    }


# ============================================================
# FALLBACK
# ============================================================

def fallback_result(
    request_row,
    reason
):

    return {

        "request_id": str(
            request_row["request_id"]
        ),

        "amount_safe_to_pay": 0.0,

        "affordability_status":
            "not_affordable",

        "recommended_payment_method":
            "not_recommended",

        "payment_plan":
            "none",

        "earliest_date_for_full_payment":
            "",

        "spending_changes_needed":
            "none",

        "decision_explanation":
            reason
    }


# ============================================================
# GENERATE OUTPUT
# ============================================================

def generate_output():

    data = prepare_data(
        load_data()
    )

    requests_df = data[
        "requests"
    ]

    results = []

    for _, request_row in requests_df.iterrows():

        try:

            result = solve_request(
                request_row,
                data
            )

        except Exception as exc:

            result = fallback_result(
                request_row,
                f"Processing error: {exc}"
            )

        results.append(result)

    columns = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation"
    ]

    output = pd.DataFrame(
        results,
        columns=columns
    )

    request_amounts = (
        requests_df
        .set_index(
            requests_df[
                "request_id"
            ].astype(str)
        )[
            "requested_amount"
        ]
    )

    output[
        "amount_safe_to_pay"
    ] = output.apply(
        lambda row: max(
            0.0,
            min(
                float(
                    row[
                        "amount_safe_to_pay"
                    ]
                ),
                float(
                    request_amounts.get(
                        str(
                            row[
                                "request_id"
                            ]
                        ),
                        0
                    )
                )
            )
        ),
        axis=1
    ).round(2)

    output.to_csv(
        OUTPUT_FILE,
        index=False
    )

    return output


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)


# ============================================================
# HOME — GET + POST
# ============================================================

@app.route(
    "/",
    methods=["GET", "POST"]
)
def home():

    # Normal page opening.
    if request.method == "GET":

        return render_template(
            "index.html"
        )

    # Form submission.
    try:

        purchase_amount = float(
            request.form.get(
                "purchase_amount",
                0
            )
        )

        current_balance = float(
            request.form.get(
                "current_balance",
                0
            )
        )

        minimum_balance = float(
            request.form.get(
                "minimum_balance",
                0
            )
        )

    except (
        TypeError,
        ValueError
    ):

        return render_template(
            "index.html",
            result={
                "status":
                    "Invalid Input",

                "message":
                    "Please enter valid numbers.",

                "remaining_balance":
                    0
            }
        )

    balance_after = (
        current_balance
        - purchase_amount
    )

    if balance_after >= minimum_balance:

        result = {

            "status":
                "Affordable Now",

            "message":
                (
                    "The purchase stays above "
                    "the minimum balance."
                ),

            "remaining_balance":
                money(balance_after)
        }

    else:

        result = {

            "status":
                "Wait",

            "message":
                (
                    "The purchase would reduce "
                    "the balance below the "
                    "required minimum."
                ),

            "remaining_balance":
                money(balance_after)
        }

    return render_template(
        "index.html",
        result=result
    )


# ============================================================
# CHECK ROUTE
# ============================================================

@app.route(
    "/check",
    methods=["GET", "POST"]
)
def check():

    if request.method == "GET":

        return render_template(
            "index.html"
        )

    return home()


# ============================================================
# COMMAND LINE
# ============================================================

if __name__ == "__main__":

    import sys

    if len(sys.argv) > 1:

        command = (
            sys.argv[1]
            .lower()
        )

        if command == "generate":

            output = generate_output()

            print()
            print(
                "======================================"
            )
            print(
                "OUTPUT GENERATED"
            )
            print(
                "======================================"
            )

            print(
                f"Rows: {len(output)}"
            )

            print(
                f"File: {OUTPUT_FILE}"
            )

            print()
            print(
                "Status counts:"
            )

            print(
                output[
                    "affordability_status"
                ].value_counts()
            )

        elif command == "web":

            app.run(
                host="0.0.0.0",
                port=5000,
                debug=True
            )

        else:

            print(
                "Usage:"
            )

            print(
                "python app.py generate"
            )

            print(
                "python app.py web"
            )

    else:

        app.run(
            host="0.0.0.0",
            port=5000,
            debug=True
        )