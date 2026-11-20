"""Annual amounts in whole INR. No CTC-to-salary inference or hidden eligibility guesses."""

from dataclasses import dataclass, field, fields


@dataclass(frozen=True)
class HRAPeriod:
    salary_basis: int
    received: int
    rent: int
    metro: bool

    def __post_init__(self):
        for name in ["salary_basis", "received", "rent"]:
            _money(name, getattr(self, name))
        if type(self.metro) is not bool:
            raise ValueError(
                "HRA metro must be explicitly true or false (Delhi, Mumbai, Kolkata, Chennai only)"
            )


def _money(name, value):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative whole-rupee integer")


@dataclass(frozen=True)
class TaxProfile:
    salary: int
    financial_year: str
    age: int
    resident: bool
    section_80c: int = 0
    nps_80ccd_1b: int = 0
    health_self: int = 0
    health_parents: int = 0
    checkup_self: int = 0
    checkup_parents: int = 0
    medical_self: int = 0
    medical_parents: int = 0
    family_senior: bool = False
    parents_senior: bool = False
    health_premium_cash: bool = False
    home_interest: int = 0
    home_loan_qualifies_2l: bool | None = None
    hra_periods: tuple = field(default_factory=tuple)

    def __post_init__(self):
        for name in [
            "salary",
            "section_80c",
            "nps_80ccd_1b",
            "health_self",
            "health_parents",
            "checkup_self",
            "checkup_parents",
            "medical_self",
            "medical_parents",
            "home_interest",
        ]:
            _money(name, getattr(self, name))
        if self.financial_year not in ["2024-25", "2025-26"]:
            raise ValueError("Supported financial years: 2024-25 and 2025-26")
        if type(self.age) is not int or not 18 <= self.age <= 120:
            raise ValueError(
                "age must be an integer from 18 to 120, at the end of the financial year"
            )
        for name in ["resident", "family_senior", "parents_senior", "health_premium_cash"]:
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be boolean")
        if (
            self.home_loan_qualifies_2l is not None
            and type(self.home_loan_qualifies_2l) is not bool
        ):
            raise ValueError("home_loan_qualifies_2l must be boolean")
        if self.home_interest and self.home_loan_qualifies_2l is None:
            raise ValueError(
                "Clarify loan eligibility: purchase/construction after 1-Apr-1999 completed within five years, or the 30,000 limit?"
            )
        if self.health_premium_cash and (self.health_self or self.health_parents):
            raise ValueError(
                "Cash premiums are not eligible under 80D; provide only eligible noncash premiums"
            )
        if self.medical_self and (
            not (self.family_senior or (self.age >= 60 and self.resident)) or self.health_self
        ):
            raise ValueError(
                "Medical expenditure needs an uninsured resident senior in the family; split member-level claims outside this simplified input"
            )
        if self.medical_parents and (not self.parents_senior or self.health_parents):
            raise ValueError("Medical expenditure needs an uninsured resident senior parent")
        if not isinstance(self.hra_periods, (tuple, list)) or any(
            not isinstance(p, HRAPeriod) for p in self.hra_periods
        ):
            raise ValueError("hra_periods must contain HRAPeriod values")
        if sum(p.received + p.salary_basis for p in self.hra_periods) > self.salary:
            raise ValueError(
                "HRA and its salary basis are components of gross salary, not additional income"
            )

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Tax input must be an object")
        unknown = set(value) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unsupported fields: {sorted(unknown)}; salary income only")
        data = dict(value)
        data["hra_periods"] = tuple(HRAPeriod(**p) for p in data.get("hra_periods", []))
        return cls(**data)
