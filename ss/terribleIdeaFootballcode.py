import itertools
import csv
import logging
from typing import Dict, List, Tuple, Iterator
import argparse

# Constants
INPUT_FILE = 'ss/footballdataShort.csv'
OUTPUT_FILE = 'teamsheet.csv'
POSITIONS = ('GK', 'DEF', 'MID', 'FWD')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_combinations(
    data: Dict[str, Dict],
    number_of_fwds: int,
    number_of_mids: int,
    number_of_gks: int,
    number_of_defs: int,
    max_value: float
) -> Iterator[Tuple[str, ...]]:
    """
    Generate combinations of groups consisting of specified numbers of FWDs, MIDs, GKs, and DEFs.
    """
    for fwd_combination in itertools.combinations(data['FWD'], number_of_fwds):
        fwd_total_value = sum(data['info'][name]['value'] for name in fwd_combination)
        if fwd_total_value > max_value:
            continue
        for mid_combination in itertools.combinations(data['MID'], number_of_mids):
            mid_total_value = sum(data['info'][name]['value'] for name in mid_combination)
            if fwd_total_value + mid_total_value > max_value:
                continue
            for def_combination in itertools.combinations(data['DEF'], number_of_defs):
                def_total_value = sum(data['info'][name]['value'] for name in def_combination)
                if fwd_total_value + mid_total_value + def_total_value > max_value:
                    continue
                for gk_combination in itertools.combinations(data['GK'], number_of_gks):
                    gk_total_value = sum(data['info'][name]['value'] for name in gk_combination)
                    if fwd_total_value + mid_total_value + def_total_value + gk_total_value <= max_value:
                        yield fwd_combination + mid_combination + def_combination + gk_combination

def calculate_group_totals(group: Tuple[str, ...], data: Dict[str, Dict]) -> Tuple[float, int]:
    """
    Calculate the total value and total points for a group
    """
    total_value = sum(data['info'][name]['value'] for name in group)
    total_points = sum(data['info'][name]['points'] for name in group)
    return total_value, total_points

def read_csv(filename: str) -> Dict[str, Dict]:
    """
    Read player information from a CSV file and store it in a dictionary
    """
    data = {pos: set() for pos in POSITIONS}
    data['info'] = {}
    try:
        with open(filename, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                name = row['Name']
                position = row['Position']
                value = float(row['Price number'])
                points = int(row['Points total'])
                data['info'][name] = {'value': value, 'points': points, 'position': position}
                if position in POSITIONS:
                    data[position].add(name)
    except FileNotFoundError:
        logging.error(f"Input file '{filename}' not found.")
        raise
    except csv.Error as e:
        logging.error(f"Error reading CSV file: {e}")
        raise
    return data

def write_results(filename: str, top_groups: List[Tuple[Tuple[str, ...], float, int]], data: Dict[str, Dict]) -> None:
    """
    Write results to CSV file
    """
    try:
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['Group', 'Names', 'Positions', 'Total Value', 'Total Points']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for i, (group, total_value, total_points) in enumerate(top_groups, start=1):
                group_names = ', '.join(group)
                group_positions = ', '.join(data['info'][name]['position'] for name in group)
                writer.writerow({
                    'Group': f'Group {i}',
                    'Names': group_names,
                    'Positions': group_positions,
                    'Total Value': total_value,
                    'Total Points': total_points
                })
    except IOError as e:
        logging.error(f"Error writing to output file: {e}")
        raise

def main(args: argparse.Namespace) -> None:
    logging.info("Starting player combination generation...")
    
    try:
        data = read_csv(args.input_file)
        logging.info(f"Data loaded from {args.input_file}")

        groups = generate_combinations(
            data, args.fwds, args.mids, args.gks, args.defs, args.max_value
        )

        top_groups = []
        for group in groups:
            total_value, total_points = calculate_group_totals(group, data)
            if total_value <= args.max_value:
                top_groups.append((group, total_value, total_points))
                top_groups.sort(key=lambda x: x[2], reverse=True)
                top_groups = top_groups[:args.top_n]

        write_results(args.output_file, top_groups, data)
        logging.info(f"Results written to {args.output_file}")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate optimal player combinations for a fantasy football team.")
    parser.add_argument('--input_file', type=str, default=INPUT_FILE, help='Input CSV file name')
    parser.add_argument('--output_file', type=str, default=OUTPUT_FILE, help='Output CSV file name')
    parser.add_argument('--max_value', type=float, default=50.0, help='Maximum allowed total value for a group')
    parser.add_argument('--top_n', type=int, default=5, help='Number of top options to keep')
    parser.add_argument('--fwds', type=int, default=2, help='Number of forwards in each group')
    parser.add_argument('--mids', type=int, default=5, help='Number of midfielders in each group')
    parser.add_argument('--gks', type=int, default=1, help='Number of goalkeepers in each group')
    parser.add_argument('--defs', type=int, default=3, help='Number of defenders in each group')

    args = parser.parse_args()
    main(args)
