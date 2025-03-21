import csv
import logging
from typing import Dict, List, Tuple
import argparse
from pulp import *
import os

# Constants
INPUT_FILE = 'footballdata.csv'
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
                position = row['Position']
                value = float(row['Price number'])
                points = float(row['Points total'])
                data['info'][name] = {'value': value, 'points': points, 'position': position}
                if position in POSITIONS:
                    data[position].append(name)
    except FileNotFoundError:
        logging.error(f"Input file '{filename}' not found.")
        raise
    except csv.Error as e:
        logging.error(f"Error reading CSV file: {e}")
        raise
    return data

def optimize_team(data: Dict[str, Dict], formation: List[int], max_value: float) -> Tuple[List[str], float, int]:
    """
    Use integer programming to optimize team selection for a given formation
    """
    # Create the problem
    prob = LpProblem("Fantasy Football Team Selection", LpMaximize)

    # Create variables
    player_vars = LpVariable.dicts("Players", data['info'].keys(), cat='Binary')

    # Objective function
    prob += lpSum([data['info'][player]['points'] * player_vars[player] for player in data['info']])

    # Constraints
    # Total value constraint
    prob += lpSum([data['info'][player]['value'] * player_vars[player] for player in data['info']]) <= max_value

    # Position constraints
    for position, count in zip(POSITIONS, formation):
        prob += lpSum([player_vars[player] for player in data['info'] if data['info'][player]['position'] == position]) == count

    # Solve the problem
    prob.solve(PULP_CBC_CMD(msg=0))

    # Check the status
    if LpStatus[prob.status] == 'Optimal':
        selected_players = [player for player in data['info'] if value(player_vars[player]) > 0.5]
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
                names = ', '.join(players)
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

        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)

        best_result = ([], 0, 0)
        best_formation = []
        all_results = []

        for formation in FORMATIONS:
            logging.info(f"Trying formation: {formation}")
            result = optimize_team(data, formation, args.max_value)
            all_results.append((formation, result[2]))  # Store formation and total points

            # Write result for this formation
            formation_str = '-'.join(map(str, formation[1:]))  # Exclude GK from formation string
            output_file = os.path.join(args.output_dir, f"formation_{formation_str}.csv")
            write_results(output_file, result, data, formation)
            logging.info(f"Results for formation {formation_str} written to {output_file}")

            if result[2] > best_result[2]:  # Compare total points
                best_result = result
                best_formation = formation

        # Write summary
        summary_file = os.path.join(args.output_dir, SUMMARY_FILE)
        write_summary(summary_file, all_results)
        logging.info(f"Summary written to {summary_file}")

        logging.info(f"Best formation: {best_formation}, Total points: {best_result[2]}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize player selection for a fantasy football team.")
    parser.add_argument('--input_file', type=str, default=INPUT_FILE, help='Input CSV file name')
    parser.add_argument('--output_dir', type=str, default=OUTPUT_DIR, help='Output directory for results')
    parser.add_argument('--max_value', type=float, default=50.0, help='Maximum allowed total value for a group')

    args = parser.parse_args()
    main(args)