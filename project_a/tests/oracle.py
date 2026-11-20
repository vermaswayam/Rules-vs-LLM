"""Independent closed-form oracle used ONLY to author frozen expected fixtures.

Production uses slab integration. This uses published cumulative bases; no imports
from the production calculator or its configuration. Official validation is separate.
"""

from decimal import Decimal, ROUND_HALF_UP


def raw_tax(income, year, regime, age=35, resident=True):
    if regime == "old":
        exempt = 500000 if resident and age >= 80 else 300000 if resident and age >= 60 else 250000
        if income <= exempt:
            return Decimal(0)
        if income <= 500000:
            return Decimal(income - exempt) * Decimal(".05")
        base = Decimal(500000 - exempt) * Decimal(".05")
        if income <= 1000000:
            return base + Decimal(income - 500000) * Decimal(".20")
        return base + 100000 + Decimal(income - 1000000) * Decimal(".30")
    if year == "2024-25":
        segments = [
            (300000, 0, "0"),
            (700000, 0, ".05"),
            (1000000, 20000, ".10"),
            (1200000, 50000, ".15"),
            (1500000, 80000, ".20"),
        ]
        lower = [0, 300000, 700000, 1000000, 1200000]
        for (upper, base, rate), start in zip(segments, lower):
            if income <= upper:
                return Decimal(base) + Decimal(income - start) * Decimal(rate)
        return Decimal(140000) + Decimal(income - 1500000) * Decimal(".30")
    for upper, base, rate, start in [
        (400000, 0, "0", 0),
        (800000, 0, ".05", 400000),
        (1200000, 20000, ".10", 800000),
        (1600000, 60000, ".15", 1200000),
        (2000000, 120000, ".20", 1600000),
        (2400000, 200000, ".25", 2000000),
    ]:
        if income <= upper:
            return Decimal(base) + Decimal(income - start) * Decimal(rate)
    return Decimal(300000) + Decimal(income - 2400000) * Decimal(".30")


def expected_tax(salary, year, regime, age=35, resident=True, old_deductions=0):
    income = max(
        0,
        salary - (50000 if regime == "old" else 75000) - (old_deductions if regime == "old" else 0),
    )
    income = int((Decimal(income) / 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) * 10
    tax = raw_tax(income, year, regime, age, resident)
    threshold = 500000 if regime == "old" else 700000 if year == "2024-25" else 1200000
    cap = 12500 if regime == "old" else 25000 if year == "2024-25" else 60000
    if resident and income <= threshold:
        tax -= min(tax, cap)
    elif resident and regime == "new":
        tax = min(tax, Decimal(income - threshold))
    surcharge = Decimal(0)
    for boundary, rate in [
        (5000000, ".10"),
        (10000000, ".15"),
        (20000000, ".25"),
        (50000000, ".37" if regime == "old" else ".25"),
    ]:
        if income > boundary:
            surcharge = Decimal(rate)
    total = tax * (1 + surcharge)
    # At each threshold use tax plus the surcharge applying AT that threshold.
    previous = Decimal(0)
    for boundary, rate in [
        (5000000, ".10"),
        (10000000, ".15"),
        (20000000, ".25"),
        (50000000, ".37" if regime == "old" else ".25"),
    ]:
        rate = Decimal(rate)
        if income > boundary and rate > previous:
            ceiling = (
                raw_tax(boundary, year, regime, age, resident) * (1 + previous) + income - boundary
            )
            total = min(total, ceiling)
        previous = rate
    final = total * Decimal("1.04")
    return int((final / 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) * 10
