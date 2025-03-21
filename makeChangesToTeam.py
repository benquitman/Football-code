import csv
import logging
from typing import Dict, List, Tuple
import argparse
from pulp import *
import os

# Constants
INPUT_FILE = 'footballdata.csv'
INITIAL_TEAM_FILE = 'team.csv'
OUTPUT_DIR = 'output'
SUMMARY_FILE = 'summary.csv'
POSITIONS = ('GK', 'DEF', 'MID', 'FWD')

# Formations to try
FORMATIONS = [
    [1, 4, 4, 2],
    [1, 4, 3, 3],
    [1, 3, 5, 2],
    [1, 4, 5, 1],
    [1, 3, 4, 3],
    [1, 5, 4, 1],
    [1, 5, 3, 2]
]

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def sanitize_name(name: str) -> str:
    return name.replace(' ', '_')

def read_csv(filename: str) -> Dict[str, Dict]:
    """
    Read player information from a CSV file and store it in a dictionary
    """
    data = {pos: [] for pos in POSITIONS}
    data['info'] = {}
    try:
       with open(filename, 'r', encoding='cp1252', errors='replace') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = row['Name']
                sanitized_name = sanitize_name(name)
                position = row['Position']
                value = float(row['Price number'])
                points = float(row['Points total'])
                data['info'][sanitized_name] = {'value': value, 'points': points, 'position': position, 'original_name': name,}
                if position in POSITIONS:
                    data[position].append(sanitized_name)
    except FileNotFoundError:
        logging.error(f"Input file '{filename}' not found.")
        raise
    except csv.Error as e:
        logging.error(f"Error reading CSV file: {e}")
        raise
    return data

def read_initial_team(filename: str) -> List[str]:
    """
    Read the initial team from a CSV file.
    """
    initial_team = []
    try:
        with open(filename, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Position'].startswith('GK'):
                    initial_team.append(sanitize_name(row['Names'].strip()))
                else:
                    names = row['Names'].split(', ')
                    initial_team.extend(sanitize_name(name.strip()) for name in names)
    except FileNotFoundError:
        logging.error(f"Initial team file '{filename}' not found.")
        raise
    except csv.Error as e:
        logging.error(f"Error reading initial team CSV file: {e}")
        raise

    # Filter out empty lines and formation information
    initial_team = [player for player in initial_team if player and not player.isdigit() and '-' not in player]

    logging.debug("Initial team players:")
    for player in initial_team:
        logging.debug(player)

    return initial_team

def make_changes_to_team(data: Dict[str, Dict], initial_team: List[str], force_replace: str, max_changes: int, max_value: float, formation: List[int]) -> Tuple[List[str], float, int]:
    """
    Use integer programming to make up to max_changes substitutions to the initial team.
    """
    all_players = set(data['info'].keys())
    initial_team_set = set(initial_team)
    available_players = list(all_players - initial_team_set)

    if force_replace and force_replace in initial_team:
        initial_team.remove(force_replace)
        initial_team_set.remove(force_replace)

    # Create the problem
    prob = LpProblem("Fantasy_Football_Team_Selection", LpMaximize)

    # Create variables
    player_vars = LpVariable.dicts("Players", all_players, cat='Binary')

    # Objective function
    prob += lpSum([data['info'][player]['points'] * player_vars[player] for player in all_players])

    # Constraints
    # Total value constraint
    prob += lpSum([data['info'][player]['value'] * player_vars[player] for player in all_players]) <= max_value

    # Position constraints
    for position, count in zip(POSITIONS, formation):
        prob += lpSum([player_vars[player] for player in all_players if data['info'][player]['position'] == position]) == count

    # Ensure initial team players are included or replaced
    num_initial_players = len(initial_team)
    prob += lpSum([player_vars[player] for player in initial_team]) >= num_initial_players - max_changes

    # Force replace constraint
    if force_replace:
        prob += player_vars[force_replace] == 0

    # Solve the problem
    prob.solve(PULP_CBC_CMD(msg=0))

    # Check the status
    if LpStatus[prob.status] == 'Optimal':
        selected_players = [player for player in all_players if value(player_vars[player]) > 0.5]
        total_value = sum(data['info'][player]['value'] for player in selected_players)
        total_points = sum(data['info'][player]['points'] for player in selected_players)
        return selected_players, total_value, total_points
    else:
        return [], 0, 0

def write_results(filename: str, result: Tuple[List[str], float, int], data: Dict[str, Dict], formation: List[int]) -> None:
    """
    Write results to CSV file, organizing players by their positions
    """
    try:
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['Position', 'Names', 'Values', 'Points']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            selected_players, total_value, total_points = result

            # Organize players by position
            players_by_position = {pos: [] for pos in POSITIONS}
            for player in selected_players:
                position = data['info'][player]['position']
                players_by_position[position].append(player)

            # Write players for each position
            for position, count in zip(POSITIONS, formation):
                players = players_by_position[position]
                names = ', '.join(data['info'][player]['original_name'] for player in players)
                values = ', '.join([f"{data['info'][player]['value']:.2f}" for player in players])
                points = ', '.join([str(data['info'][player]['points']) for player in players])
                
                writer.writerow({
                    'Position': f"{position} ({count})",
                    'Names': names,
                    'Values': values,
                    'Points': points
                })

            # Write total value and points
            writer.writerow({
                'Position': 'Total',
                'Names': '',
                'Values': f"{total_value:.2f}",
                'Points': str(total_points)
            })

            # Write formation
            writer.writerow({
                'Position': 'Formation',
                'Names': '-'.join(map(str, formation[1:])),  # Exclude GK from formation string
                'Values': '',
                'Points': ''
            })

    except IOError as e:
        logging.error(f"Error writing to output file: {e}")
        raise

def write_summary(filename: str, results: List[Tuple[List[int], int]]) -> None:
    """
    Write summary of all formations and their total points
    """
    try:
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['Formation', 'Total Points']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for formation, total_points in results:
                writer.writerow({
                    'Formation': '-'.join(map(str, formation[1:])),  # Exclude GK from formation string
                    'Total Points': total_points
                })

    except IOError as e:
        logging.error(f"Error writing to summary file: {e}")
        raise

def main(args: argparse.Namespace) -> None:
    logging.info("Starting team optimization...")
    
    try:
        data = read_csv(args.input_file)
        logging.info(f"Data loaded from {args.input_file}")

        initial_team = read_initial_team(args.initial_team_file)
        logging.info(f"Initial team loaded from {args.initial_team_file}")

        if args.force_replace:
            logging.info(f"Force replacing player: {args.force_replace}")
            force_replace = sanitize_name(args.force_replace)
        else:
            force_replace = None
        
        best_team = []
        best_value = 0
        best_points = 0
        best_formation = []

        all_results = []

        for formation in FORMATIONS:
            optimized_team, total_value, total_points = make_changes_to_team(data, initial_team, force_replace, args.max_changes, args.max_value, formation)
            all_results.append((formation, total_points))

            if total_points > best_points:
                best_team = optimized_team
                best_value = total_value
                best_points = total_points
                best_formation = formation
            
            formation_str = '-'.join(map(str, formation[1:]))
            output_file = os.path.join(args.output_dir, f'optimized_team_{formation_str}.csv')
            write_results(output_file, (optimized_team, total_value, total_points), data, formation)
            logging.info(f"Optimized team for formation {formation_str} written to {output_file}")

        # Write summary of all formations
        summary_file = os.path.join(args.output_dir, SUMMARY_FILE)
        write_summary(summary_file, all_results)
        logging.info(f"Summary written to {summary_file}")

        logging.info(f"Best formation: {best_formation}, Total points: {best_points}")

    except Exception as e:
        logging.error(f"An error occurred: {e}") 
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize player selection for a fantasy football team.")
    parser.add_argument('--input_file', type=str, default=INPUT_FILE, help='Input CSV file name')
    parser.add_argument('--initial_team_file', type=str, default=INITIAL_TEAM_FILE, help='Initial team CSV file name')
    parser.add_argument('--output_dir', type=str, default=OUTPUT_DIR, help='Output directory for results')
    parser.add_argument('--max_value', type=float, default=50.0, help='Maximum allowed total value for a group')
    parser.add_argument('--max_changes', type=int, default=5, help='Maximum number of changes allowed')
    parser.add_argument('--force_replace', type=str, default="", help='Player to be forced replaced')
    args = parser.parse_args()
    main(args)