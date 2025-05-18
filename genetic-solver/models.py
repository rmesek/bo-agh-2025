import copy
from bisect import bisect
from dataclasses import dataclass
from typing import TypeAlias

Time: TypeAlias = tuple[int, int]  # (hour, minute)


def validate_range(value, min_val, max_val, name):
    """Validate that a value falls within the specified range."""
    if not min_val <= value <= max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {value}")


def validate_coordinates(location):
    """Validate location coordinates."""
    if len(location) != 2:
        raise ValueError(f"Location must have exactly 2 coordinates, got {location}")


def validate_time(time: Time) -> None:
    """Validate time format."""
    if not (0 <= time[0] < 24 and 0 <= time[1] < 60):
        raise ValueError(f"Invalid time format: {time}. Must be (hour, minute).")


def time_to_minutes(time: Time) -> int:
    """Convert time to minutes."""
    return time[0] * 60 + time[1]


def time_diff(time1: Time, time2: Time) -> int:
    """Calculate the difference in minutes between two times."""
    total_minutes1 = time_to_minutes(time1)
    total_minutes2 = time_to_minutes(time2)
    return (total_minutes2 - total_minutes1) % 1440  # Wrap around after 24 hours


def time_add(time: Time, minutes_to_add: int) -> Time:
    """Add minutes to a time."""
    total_minutes = time[0] * 60 + time[1] + minutes_to_add
    total_minutes %= 1440  # Wrap around after 24 hours
    return divmod(total_minutes, 60)


@dataclass
class Restaurant:
    id: str
    name: str
    location: tuple[float, float]  # [latitude, longitude]
    cuisine_type: str
    average_price: int
    rating: float
    available_hours: tuple[Time, Time]  # [opening_time, closing_time]
    traffic_pattern: list[tuple[Time, float]]

    def __post_init__(self):
        validate_coordinates(self.location)
        validate_range(self.average_price, 0, 100, "Average price")
        validate_range(self.rating, 0, 5, "Rating")
        validate_time(self.available_hours[0])
        validate_time(self.available_hours[1])
        for time, traffic in self.traffic_pattern:
            validate_time(time)
            validate_range(traffic, 0, 100, "Traffic value")
        self.traffic_pattern.sort(key=lambda x: x[0])  # Sort by time

    def __eq__(self, value: object) -> bool:
        if isinstance(value, Restaurant):
            return self.id == value.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"Restaurant({self.id}, {self.name})"

    def copy(self) -> "Restaurant":
        return copy.deepcopy(self)

    def traffic(self, time: Time) -> float:
        """Get traffic intensity closest to the given time."""
        if not self.traffic_pattern:
            return 0.0
        idx = bisect(self.traffic_pattern, (time, 0))
        if idx == 0:
            return self.traffic_pattern[0][1]
        elif idx == len(self.traffic_pattern):
            return self.traffic_pattern[-1][1]
        prev_diff = time_diff(self.traffic_pattern[idx - 1][0], time)
        next_diff = time_diff(time, self.traffic_pattern[idx][0])
        return (
            self.traffic_pattern[idx - 1][1]
            if prev_diff <= next_diff
            else self.traffic_pattern[idx][1]
        )


@dataclass
class Person:
    id: str
    name: str
    location: tuple[float, float]  # [latitude, longitude]
    budget: int
    preferred_cuisines: set[str]
    restricted_restaurants_ids: set[str]
    available_hours: tuple[Time, Time]  # [start_time, end_time]

    def __post_init__(self):
        validate_coordinates(self.location)
        validate_range(self.budget, 0, 100, "Budget")
        validate_time(self.available_hours[0])
        validate_time(self.available_hours[1])

    def __eq__(self, value: object) -> bool:
        if isinstance(value, Person):
            return self.id == value.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"Person({self.id}, {self.name})"

    def copy(self) -> "Person":
        return copy.deepcopy(self)

    def distance(self, other: "Restaurant | Person") -> float:
        dx = self.location[0] - other.location[0]
        dy = self.location[1] - other.location[1]
        return (dx * dx + dy * dy) ** 0.5

    def find_restricted(self, all_restaurants: list[Restaurant]) -> set[Restaurant]:
        """
        Find restricted restaurants based on the person's preferences.

        Args:
            all_restaurants (list[Restaurant]): List of all restaurants.

        Returns:
            set[Restaurant]: Set of restricted restaurants.
        """
        return {r for r in all_restaurants if r.id in self.restricted_restaurants_ids}
