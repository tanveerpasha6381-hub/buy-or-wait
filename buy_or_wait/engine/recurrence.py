import pandas as pd


def detect_recurring_events(user_events):
    """
    Detect simple recurring financial patterns from historical events.

    We look for the same user + category + direction + similar description
    appearing multiple times with approximately regular intervals.
    """

    events = user_events.copy()

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events["amount"] = pd.to_numeric(
        events["amount"],
        errors="coerce"
    )

    events = events.dropna(
        subset=["event_date", "amount"]
    )

    recurring = []

    # Group by user, direction and category.
    groups = events.groupby(
        ["user_id", "direction", "category"],
        dropna=False
    )

    for (user_id, direction, category), group in groups:

        group = group.sort_values("event_date").copy()

        # Need at least 2 records to detect a pattern.
        if len(group) < 2:
            continue

        dates = group["event_date"].tolist()

        intervals = []

        for i in range(1, len(dates)):
            days = (dates[i] - dates[i - 1]).days
            intervals.append(days)

        if not intervals:
            continue

        median_interval = float(
            pd.Series(intervals).median()
        )

        # Keep likely recurring intervals:
        # weekly-ish, biweekly-ish, monthly-ish.
        if not (
            5 <= median_interval <= 10
            or
            12 <= median_interval <= 18
            or
            25 <= median_interval <= 35
        ):
            continue

        # Check that intervals are reasonably consistent.
        consistent = sum(
            abs(x - median_interval) <= 4
            for x in intervals
        )

        consistency_ratio = consistent / len(intervals)

        if consistency_ratio < 0.60:
            continue

        # Use the recent typical amount.
        recent = group.tail(min(3, len(group)))

        median_amount = float(
            recent["amount"].median()
        )

        last_date = group["event_date"].max()

        description = str(
            recent.iloc[-1]["description"]
        )

        recurring.append({
            "user_id": user_id,
            "direction": direction,
            "category": category,
            "description": description,
            "interval_days": round(median_interval),
            "amount": median_amount,
            "last_date": last_date,
            "confidence": round(consistency_ratio, 2)
        })

    return pd.DataFrame(recurring)


def project_recurring_events(
    recurring_events,
    start_date,
    end_date
):
    """
    Project detected recurring events into the future.
    """

    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    projected = []

    if recurring_events.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "direction",
                "category",
                "description",
                "amount",
                "event_date",
                "source"
            ]
        )

    for _, pattern in recurring_events.iterrows():

        interval = int(pattern["interval_days"])

        next_date = (
            pd.Timestamp(pattern["last_date"])
            + pd.Timedelta(days=interval)
        )

        while next_date <= end_date:

            if next_date >= start_date:

                projected.append({
                    "user_id": pattern["user_id"],
                    "direction": pattern["direction"],
                    "category": pattern["category"],
                    "description": pattern["description"],
                    "amount": pattern["amount"],
                    "event_date": next_date,
                    "source": "recurring_projection"
                })

            next_date += pd.Timedelta(days=interval)

    return pd.DataFrame(projected)