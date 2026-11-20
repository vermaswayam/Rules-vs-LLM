"""Reference distributions learned only from the training partition."""

from collections import Counter, defaultdict
import math


class Reference:
    def __init__(self, rows):
        self.columns = set(rows[0])
        self.descriptors = defaultdict(set)
        self.pairs = Counter()
        self.complaints = Counter()
        self.zip_boroughs = defaultdict(set)
        self.zip_pairs = Counter()
        self.zips = Counter()
        self.agency_nulls = defaultdict(lambda: [0, 0])
        self.types = defaultdict(Counter)
        self.coordinate_samples = {"latitude": [], "longitude": []}
        self.status_tokens = defaultdict(Counter)
        self.status_counts = Counter()
        self.date_shapes = Counter()
        self.durations = []
        for row in rows:
            from .data import timestamp
            import re

            if row.get("created_date"):
                self.date_shapes[re.sub(r"\d", "D", row["created_date"])] += 1
            created, closed = timestamp(row.get("created_date")), timestamp(row.get("closed_date"))
            if created and closed and closed >= created:
                self.durations.append((closed - created).total_seconds())
            c, d = row.get("complaint_type"), row.get("descriptor")
            if c and d:
                self.descriptors[c].add(d)
                self.pairs[c, d] += 1
                self.complaints[c] += 1
            zip_, borough = row.get("incident_zip"), row.get("borough")
            if zip_ and borough and borough != "Unspecified":
                self.zip_boroughs[zip_].add(borough)
                self.zip_pairs[zip_, borough] += 1
                self.zips[zip_] += 1
            agency = row.get("agency")
            self.agency_nulls[agency][0] += int(row.get("descriptor") is None)
            self.agency_nulls[agency][1] += 1
            for key, value in row.items():
                if value is not None:
                    self.types[key][type(value).__name__] += 1
            for key in self.coordinate_samples:
                if type(row.get(key)) is float:
                    self.coordinate_samples[key].append(row[key])
            status = row.get("status")
            self.status_counts[status] += 1
            for token in set(tokens(row.get("resolution_description") or "")):
                self.status_tokens[status][token] += 1
        self.expected_types = {k: counts.most_common(1)[0][0] for k, counts in self.types.items()}
        self.minimum_duration = min(self.durations, default=0)
        self.geo = {}
        for key, samples in self.coordinate_samples.items():
            samples.sort()
            middle = samples[len(samples) // 2]
            deviations = sorted(abs(v - middle) for v in samples)
            self.geo[key] = (middle, max(deviations[len(deviations) // 2], 0.001))
        self.all_descriptors = set().union(*self.descriptors.values())
        self.all_tokens = set().union(*(set(c) for c in self.status_tokens.values()))

    def status_score(self, text, status):
        # Bernoulli-like token log-likelihood score; simple, inspectable baseline.
        words = set(tokens(text))
        return sum(
            math.log((self.status_tokens[status][word] + 1) / (self.status_counts[status] + 2))
            for word in words
            if word in self.all_tokens
        )


def tokens(text):
    import re

    return re.findall(r"[a-z]+", str(text).lower())
