from typing import Any
from data_loader import find_json_files, load_data, parse_data
from models import Person, Restaurant

# ANSII color codes
HEADER = "\033[95m"
OKBLUE = "\033[94m"
OKGREEN = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"


def find_solution(restaurants: list[Restaurant], people: list[Person]) -> Any:
    """
    Find a solution for the given restaurants and people using a genetic algorithm.
    """
    raise NotImplementedError("Genetic algorithm not implemented yet.")


def main(json_path: str | None = None):
    for json_file in find_json_files(json_path):
        print(f"{HEADER}Processing file: {json_file}{ENDC}")
        try:
            data = load_data(json_file)
            restaurants, people = parse_data(data)
        except Exception as e:
            print(f"{FAIL}Error processing {json_file}: {e}{ENDC}")
            continue

        print(f"Loaded {len(restaurants)} restaurants and {len(people)} people.")
        solution = find_solution(restaurants, people)
        print(f"{OKGREEN}Solution found!{ENDC}")
        print(solution)
        print()


if __name__ == "__main__":
    DATA_PATH = r"data/6-3-simple-data.json"
    main(json_path=None)
