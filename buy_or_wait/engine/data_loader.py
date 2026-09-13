import pandas as pd
from pathlib import Path


# Project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Data folder
DATA_DIR = BASE_DIR / "data"


def load_data():
    """
    Load all HackerRank CSV files and return them
    in a dictionary.
    """

    data = {}

    data["requests"] = pd.read_csv(DATA_DIR / "requests.csv")
    data["profiles"] = pd.read_csv(DATA_DIR / "financial_profiles.csv")
    data["events"] = pd.read_csv(DATA_DIR / "financial_events.csv")
    data["payment_options"] = pd.read_csv(
        DATA_DIR / "request_payment_options.csv"
    )
    data["messages"] = pd.read_csv(DATA_DIR / "messages.csv")
    data["images"] = pd.read_csv(DATA_DIR / "images.csv")
    data["exchange_rates"] = pd.read_csv(DATA_DIR / "exchange_rates.csv")

    return data


if __name__ == "__main__":
    data = load_data()

    print("\n===== DATA LOADED SUCCESSFULLY =====")

    for name, dataframe in data.items():
        print(f"{name}: {len(dataframe)} rows")

    print("\n===== LOADER TEST COMPLETE =====")