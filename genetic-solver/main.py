import random
from typing import TypeAlias

from data_loader import find_json_files, load_data, parse_data
from models import Person, Restaurant, Time, time_add, time_to_minutes, validate_time

# ANSII color codes
HEADER = "\033[95m"
OKBLUE = "\033[94m"
OKGREEN = "\033[92m"
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"

# --- Genetic Algorithm Parameters ---
POPULATION_SIZE = 100  # Number of individuals in the population
NUM_GENERATIONS = 150  # Number of generations to run the algorithm
MUTATION_RATE = 0.15  # Probability of an individual mutating
TOURNAMENT_SIZE = 5  # Number of individuals in a selection tournament
ELITISM_COUNT = 2  # Number of best individuals to carry over to the next generation
TIME_SLOTS_MINUTES = [0, 15, 30, 45]  # Discrete minute slots for time selection

# Type alias for an individual in the population
Chromosome: TypeAlias = tuple[Restaurant, Time]


# --- Helper function for time validation ---
def is_time_in_range(event_time: Time, range_start: Time, range_end: Time) -> bool:
    """
    Checks if event_time is within the [range_start, range_end).
    Handles ranges that span across midnight.
    """
    # Validate inputs to prevent errors with time_to_minutes
    try:
        validate_time(event_time)
        validate_time(range_start)
        validate_time(range_end)
    except ValueError:
        return False  # Invalid time format means it cannot be in range

    event_m = time_to_minutes(event_time)
    start_m = time_to_minutes(range_start)
    end_m = time_to_minutes(range_end)

    if start_m == end_m:
        # If start and end are 00:00, it means 24 hours.
        # Otherwise (e.g. 08:00 to 08:00), it means 0 hours duration (closed).
        return start_m == 0  # True if ((0,0), (0,0)) -> 24h

    if start_m < end_m:  # Same day range (e.g., 09:00 - 17:00)
        return start_m <= event_m < end_m
    else:  # Overnight range (e.g., 22:00 - 02:00)
        return event_m >= start_m or event_m < end_m


# --- Genetic Algorithm Core Functions ---


def create_individual(restaurants: list[Restaurant]) -> Chromosome | None:
    """
    Creates a random individual (chromosome).
    A chromosome is a tuple of (Restaurant, Time).
    Returns None if no restaurants are available (though guarded in find_solution).
    """
    if not restaurants:  # Should ideally not be hit if called from find_solution post-check
        return None
    selected_restaurant = random.choice(restaurants)

    # Generate a random time: random hour, random minute from TIME_SLOTS_MINUTES
    hour = random.randint(0, 23)
    minute = random.choice(TIME_SLOTS_MINUTES)
    selected_time: Time = (hour, minute)

    return selected_restaurant, selected_time


def calculate_fitness(individual: Chromosome, people: list[Person]) -> float:
    """
    Calculates the fitness of an individual.
    Higher fitness is better. Returns float('-inf') for invalid solutions.
    """
    restaurant, chosen_time = individual
    fitness = 0.0

    # --- Hard Constraints ---
    # These must be met for a solution to be considered valid.
    # If any constraint is violated, fitness is float('-inf').

    # 1. Restaurant Open?
    if not is_time_in_range(chosen_time, restaurant.available_hours[0], restaurant.available_hours[1]):
        return float("-inf")

    # 2. People-specific constraints
    if not people:  # If there are no people, it's trivially valid from people's perspective
        pass  # No further checks needed for people
    else:
        for person in people:
            # Person available?
            if not is_time_in_range(chosen_time, person.available_hours[0], person.available_hours[1]):
                return float("-inf")

            # Budget met?
            if restaurant.average_price > person.budget:
                return float("-inf")

            # Restaurant restricted?
            if restaurant.id in person.restricted_restaurants_ids:
                return float("-inf")

    # --- Soft Scores (applied only if all hard constraints are met) ---
    # These contribute to how "good" a valid solution is.

    # 1. Restaurant Rating (e.g., rating 0-5 scaled to 0-100 points)
    fitness += restaurant.rating * 20.0  # Max 100 points for 5-star rating

    # 2. Cuisine Preferences (e.g., 15 points for each person whose preference is met)
    num_cuisine_matches = 0
    if people:  # Only calculate if there are people
        for person in people:
            if restaurant.cuisine_type in person.preferred_cuisines:
                num_cuisine_matches += 1
        # Using a fixed score per match for simplicity, can be normalized by len(people) if preferred
        fitness += num_cuisine_matches * 15.0

    # 3. Travel Distance (penalty based on average distance)
    #    Lower distance is better.
    if people:  # Only calculate if there are people
        total_distance = sum(person.distance(restaurant) for person in people)
        average_distance = total_distance / len(people)
        # The penalty should increase with distance.
        fitness -= average_distance * 2.0  # Adjust multiplier as needed

    # 4. Restaurant Traffic (penalty based on traffic level)
    #    Lower traffic (0-100) is better.
    current_traffic = restaurant.traffic(chosen_time)
    fitness -= current_traffic * 0.5  # Adjust multiplier

    return fitness


def selection(population_with_fitness: list[tuple[Chromosome, float]], tournament_size: int) -> Chromosome:
    """
    Selects an individual using tournament selection.
    """
    if not population_with_fitness:
        raise ValueError("Population is empty, cannot perform selection.")

    actual_tournament_size = min(tournament_size, len(population_with_fitness))

    tournament_contenders = random.sample(population_with_fitness, actual_tournament_size)
    tournament_contenders.sort(key=lambda x: x[1], reverse=True)  # Sort by fitness (descending)
    return tournament_contenders[0][0]  # Return the chromosome of the best contender


def crossover(parent1: Chromosome, parent2: Chromosome) -> tuple[Chromosome, Chromosome]:
    """
    Performs crossover between two parents to produce two offspring.
    Offspring 1: Restaurant from Parent 1, Time from Parent 2
    Offspring 2: Restaurant from Parent 2, Time from Parent 1
    """
    offspring1_restaurant = parent1[0]
    offspring1_time = parent2[1]

    offspring2_restaurant = parent2[0]
    offspring2_time = parent1[1]

    return (offspring1_restaurant, offspring1_time), (offspring2_restaurant, offspring2_time)


def mutate(individual: Chromosome, all_restaurants: list[Restaurant]) -> Chromosome:
    """
    Performs mutation on an individual.
    An individual's restaurant or time might change.
    """
    restaurant, time = individual
    mutated_restaurant = restaurant
    mutated_time = time

    # Mutate restaurant part (50% chance to change restaurant if this individual is chosen for mutation)
    if random.random() < 0.5:
        if all_restaurants:  # Ensure there are restaurants to choose from
            mutated_restaurant = random.choice(all_restaurants)

    # Mutate time part (50% chance to change time if this individual is chosen for mutation)
    if random.random() < 0.5:
        # Small shift in time (e.g., +/- 15, 30, 45, 60 minutes)
        shift_options = [-60, -45, -30, -15, 15, 30, 45, 60]  # minutes
        time_shift_minutes = random.choice(shift_options)
        mutated_time = time_add(time, time_shift_minutes)

    return mutated_restaurant, mutated_time


def find_solution(restaurants: list[Restaurant], people: list[Person]) -> tuple[Restaurant, Time, float] | None:
    """
    Finds a solution for the given restaurants and people using a genetic algorithm.
    Returns a tuple (best_restaurant, best_time, best_fitness_score) or None if no solution found.
    """
    if not restaurants:
        print(f"{WARNING}No restaurants provided to the genetic algorithm.{ENDC}")
        return None

    # Initialize population
    population: list[Chromosome] = []
    for _ in range(POPULATION_SIZE):
        ind = create_individual(restaurants)
        if ind:
            population.append(ind)

    if not population:
        print(f"{FAIL}Could not initialize any individuals. This is unexpected. Check restaurant data or POPULATION_SIZE.{ENDC}")
        return None

    best_solution_overall: tuple[Restaurant, Time, float] | None = None

    print(f"{OKBLUE}Starting Genetic Algorithm: {NUM_GENERATIONS} generations, {POPULATION_SIZE} population size...{ENDC}")

    for generation in range(NUM_GENERATIONS):
        # Calculate fitness for each individual
        population_with_fitness: list[tuple[Chromosome, float]] = []
        for ind_chromosome in population:
            fitness = calculate_fitness(ind_chromosome, people)
            population_with_fitness.append((ind_chromosome, fitness))

        # Sort population by fitness (descending)
        population_with_fitness.sort(key=lambda x: x[1], reverse=True)

        # Update best solution found so far
        current_best_chromosome, current_best_fitness = population_with_fitness[0]

        if best_solution_overall is None or (current_best_fitness > float("-inf") and current_best_fitness > best_solution_overall[2]):
            best_solution_overall = (current_best_chromosome[0], current_best_chromosome[1], current_best_fitness)
            if current_best_fitness > float("-inf"):
                print(f"{OKGREEN}Gen {generation + 1}: New best! Fitness: {current_best_fitness:.2f}, Restaurant: {current_best_chromosome[0].name}, Time: {current_best_chromosome[1][0]:02d}:{current_best_chromosome[1][1]:02d}{ENDC}")

        # Elitism: Carry over the best individuals
        next_population: list[Chromosome] = [item[0] for item in population_with_fitness[:ELITISM_COUNT]]

        # Generate the rest of the new population using selection, crossover, and mutation
        if not population_with_fitness or population_with_fitness[0][1] == float("-inf"):
            print(f"{WARNING}Gen {generation + 1}: Population lacks valid individuals for breeding. Re-initializing some...{ENDC}")
            num_to_reinitialize = POPULATION_SIZE // 10
            for _ in range(num_to_reinitialize):
                if len(next_population) < POPULATION_SIZE:
                    new_ind = create_individual(restaurants)
                    if new_ind:
                        next_population.append(new_ind)
            fill_count = 0
            while len(next_population) < POPULATION_SIZE and fill_count < len(population_with_fitness):
                next_population.append(population_with_fitness[fill_count][0])
                fill_count += 1
            while len(next_population) < POPULATION_SIZE:
                new_ind = create_individual(restaurants)
                if new_ind:
                    next_population.append(new_ind)
        else:
            while len(next_population) < POPULATION_SIZE:
                parent1 = selection(population_with_fitness, TOURNAMENT_SIZE)
                parent2 = selection(population_with_fitness, TOURNAMENT_SIZE)

                offspring1, offspring2 = crossover(parent1, parent2)

                if random.random() < MUTATION_RATE:
                    offspring1 = mutate(offspring1, restaurants)
                if random.random() < MUTATION_RATE:
                    offspring2 = mutate(offspring2, restaurants)

                next_population.append(offspring1)
                if len(next_population) < POPULATION_SIZE:
                    next_population.append(offspring2)

        population = next_population

        if (generation + 1) % 20 == 0 or generation == NUM_GENERATIONS - 1:
            if best_solution_overall and best_solution_overall[2] > float("-inf"):
                print(f"Gen {generation + 1}/{NUM_GENERATIONS} processed. Current best fitness: {best_solution_overall[2]:.2f}")
            else:
                print(f"Gen {generation + 1}/{NUM_GENERATIONS} processed. No valid solution found yet.")

    if best_solution_overall and best_solution_overall[2] > float("-inf"):
        print(f"{OKGREEN}Genetic Algorithm finished.{ENDC}")
        return best_solution_overall
    else:
        print(f"{FAIL}No suitable solution found after {NUM_GENERATIONS} generations.{ENDC}")
        return None


def print_solution_details(solution_tuple: tuple[Restaurant, Time, float], people: list[Person]):
    """
    Prints the details of the best solution found by the genetic algorithm.
    """
    best_restaurant, best_time, best_fitness = solution_tuple
    print(f"\n{OKGREEN}--- Optimal Meeting Plan Found ---{ENDC}")
    print(f"  Restaurant: {OKBLUE}{best_restaurant.name}{ENDC} (ID: {best_restaurant.id})")
    print(f"  Cuisine: {best_restaurant.cuisine_type}, Rating: {best_restaurant.rating}/5, Avg Price: ${best_restaurant.average_price}")
    print(f"  Meeting Time: {OKBLUE}{best_time[0]:02d}:{best_time[1]:02d}{ENDC}")
    print(f"  Predicted Traffic: {best_restaurant.traffic(best_time)}%")
    print(f"  Fitness Score: {OKGREEN}{best_fitness:.2f}{ENDC}")

    print(f"\n{HEADER}Solution Details & Checks:{ENDC}")
    print(f"  Restaurant Open Hours: {best_restaurant.available_hours[0][0]:02d}:{best_restaurant.available_hours[0][1]:02d} - {best_restaurant.available_hours[1][0]:02d}:{best_restaurant.available_hours[1][1]:02d}")
    is_rest_open = is_time_in_range(best_time, best_restaurant.available_hours[0], best_restaurant.available_hours[1])
    print(f"  Restaurant Open at Meeting Time? {'Yes' if is_rest_open else 'No'}")

    if people:
        for p_idx, person in enumerate(people):
            print(f"\n  Person {p_idx + 1}: {person.name}")
            print(f"    Available: {person.available_hours[0][0]:02d}:{person.available_hours[0][1]:02d} - {person.available_hours[1][0]:02d}:{person.available_hours[1][1]:02d}")
            is_person_avail = is_time_in_range(best_time, person.available_hours[0], person.available_hours[1])
            print(f"    Available at Meeting Time? {'Yes' if is_person_avail else 'No'}")
            print(f"    Budget: ${person.budget} (Restaurant Avg Price: ${best_restaurant.average_price}) - OK? {'Yes' if best_restaurant.average_price <= person.budget else 'No'}")
            print(f"    Preferred Cuisines: {person.preferred_cuisines} (Restaurant: {best_restaurant.cuisine_type}) - Match? {'Yes' if best_restaurant.cuisine_type in person.preferred_cuisines else 'No'}")
            is_restricted = best_restaurant.id in person.restricted_restaurants_ids
            print(f"    Restaurant Restricted? {'Yes' if is_restricted else 'No'}")
            print(f"    Distance to Restaurant: {person.distance(best_restaurant):.2f} units")
    else:
        print("\n  No specific people constraints to check as the 'people' list is empty.")


def main(json_path: str | None = None):
    """
    Main function to load data, run the genetic algorithm, and print results.
    """
    for json_file in find_json_files(json_path):
        print(f"{HEADER}Processing file: {json_file}{ENDC}")
        try:
            data = load_data(json_file)
            restaurants, people = parse_data(data)
        except Exception as e:
            print(f"{FAIL}Error processing {json_file}: {e}{ENDC}")
            continue

        print(f"Loaded {len(restaurants)} restaurants and {len(people)} people.")

        solution_tuple = find_solution(restaurants, people)

        if solution_tuple:
            print_solution_details(solution_tuple, people)
        else:
            print(f"{FAIL}No suitable meeting plan was found for {json_file}.{ENDC}")
        print("-" * 40 + "\n")


if __name__ == "__main__":
    DATA_PATH = r"data/6-3-simple-data.json"
    main(json_path=None)
