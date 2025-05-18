import json
from pathlib import Path

from models import Person, Restaurant


def find_json_files(json_path: str | None = None) -> list[Path]:
    """
    Get a list of all JSON files in the specified path.
    If no path is specified, use main /data directory.
    """
    if json_path is None:
        # get the path based on the current file's location
        path = Path(__file__).parent.parent / "data"
    else:
        # use the provided directory
        path = Path(json_path)

    if path.is_file():
        return [path]
    elif path.is_dir():
        # get all json files in the directory
        json_files = list(path.glob("*.json"))
        if not json_files:
            print(f"No JSON files found in {path}")
        return json_files
    else:
        print(f"Provided path is neither a file nor a directory: {path}")
        return []


def parse_restaurant(data: dict) -> Restaurant:
    """
    Parse restaurant data from a dictionary to a Restaurant object.

    Args:
        data (dict): Dictionary containing restaurant data.

    Returns:
        Restaurant: Restaurant object.
    """
    opening_parts = data["openingHours"][0].split(":")
    closing_parts = data["openingHours"][1].split(":")

    opening_time = (int(opening_parts[0]), int(opening_parts[1]))
    closing_time = (int(closing_parts[0]), int(closing_parts[1]))

    traffic_pattern = [
        ((int(item["hour"]), int(item["minute"])), item["value"])
        for item in data["trafficPattern"]
    ]

    return Restaurant(
        id=data["_id"],
        name=data["name"],
        location=tuple(data["location"]),
        cuisine_type=data["cuisineType"],
        average_price=data["averagePrice"],
        rating=data["rating"],
        available_hours=(opening_time, closing_time),
        traffic_pattern=traffic_pattern,
    )


def parse_person(data: dict) -> Person:
    """
    Parse person data from a dictionary to a Person object.

    Args:
        data (dict): Dictionary containing person data.

    Returns:
        Person: Person object.
    """
    start_time_parts = data["availableTimeRange"][0].split(":")
    end_time_parts = data["availableTimeRange"][1].split(":")

    start_time = (int(start_time_parts[0]), int(start_time_parts[1]))
    end_time = (int(end_time_parts[0]), int(end_time_parts[1]))

    return Person(
        id=data["_id"],
        name=data["name"],
        location=tuple(data["location"]),
        budget=data["budget"],
        preferred_cuisines=set(data["preferredCuisines"]),
        restricted_restaurants_ids=data["restrictedRestaurants"],
        available_hours=(start_time, end_time),
    )


def parse_data(data: dict) -> tuple[list[Restaurant], list[Person]]:
    """
    Parse data from a dictionary to lists of Restaurant and Person objects.

    Args:
        data (dict): Dictionary containing 'restaurants' and 'people'.

    Returns:
        tuple[list[Restaurant], list[Person]]: Tuple containing lists of Restaurant and Person objects.
    """
    restaurants = [parse_restaurant(item) for item in data["restaurants"]]
    people = [parse_person(item) for item in data["people"]]

    restaurant_ids = {restaurant.id for restaurant in restaurants}
    if len(restaurant_ids) != len(restaurants):
        raise ValueError("Duplicate restaurant IDs found.")

    person_ids = {person.id for person in people}
    if len(person_ids) != len(people):
        raise ValueError("Duplicate person IDs found.")

    return restaurants, people


def load_data(path: Path) -> dict[str, list[dict]]:
    """
    Load data from a JSON file and return it as a dictionary.

    Args:
        path (Path): Path to the JSON file.

    Returns:
        dict[str, list[dict]]: Dictionary containing 'restaurants' and 'people'.
    """
    with open(path, "r") as file:
        data = json.load(file)
    return data
