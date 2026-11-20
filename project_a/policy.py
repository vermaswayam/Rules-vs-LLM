"""Hand-authored policy. Year is an explicit input, never the machine's date."""


def hand_policy(year):
    if year not in ["2024-25", "2025-26"]:
        raise ValueError("Unsupported financial year")
    return {
        "financial_year": year,
        "standard_old": 50000,
        "standard_new": 75000,
        "old_slabs": [[250000, "0"], [500000, "0.05"], [1000000, "0.20"], [None, "0.30"]],
        "new_slabs": (
            [
                [300000, "0"],
                [700000, "0.05"],
                [1000000, "0.10"],
                [1200000, "0.15"],
                [1500000, "0.20"],
                [None, "0.30"],
            ]
            if year == "2024-25"
            else [
                [400000, "0"],
                [800000, "0.05"],
                [1200000, "0.10"],
                [1600000, "0.15"],
                [2000000, "0.20"],
                [2400000, "0.25"],
                [None, "0.30"],
            ]
        ),
        "rebate_old_threshold": 500000,
        "rebate_old_cap": 12500,
        "rebate_new_threshold": 700000 if year == "2024-25" else 1200000,
        "rebate_new_cap": 25000 if year == "2024-25" else 60000,
        "cap_80c": 150000,
        "cap_nps": 50000,
        "health_regular": 25000,
        "health_senior": 50000,
        "checkup_cap": 5000,
        "home_qualifying": 200000,
        "home_other": 30000,
        "surcharge_old": [
            [5000000, "0.10"],
            [10000000, "0.15"],
            [20000000, "0.25"],
            [50000000, "0.37"],
        ],
        "surcharge_new": [[5000000, "0.10"], [10000000, "0.15"], [20000000, "0.25"]],
        "cess": "0.04",
    }
