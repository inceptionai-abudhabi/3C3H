# Copyright 2025 G42 General Trading LLC team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import glob
import argparse
import logging
import sys
from collections import defaultdict

def setup_logging():
    """
    Configures the logging settings.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def get_judged_json_files(directory, suffix="_judged.json"):
    """
    Retrieves a list of judged JSON files in the specified directory.

    Args:
        directory (str): The directory to search for judged JSON files.
        suffix (str): The suffix that judged files have (default is "_judged.json").

    Returns:
        list: A list of judged JSON file paths.
    """
    pattern = os.path.join(directory, f"*{suffix}")
    judged_files = glob.glob(pattern)
    logging.info(f"Found {len(judged_files)} judged JSON files in {directory}.")
    return judged_files

def load_existing_results(results_file):
    """
    Loads the existing results from the output file if it exists.

    Args:
        results_file (str): The path to the results JSON file.

    Returns:
        list: Existing results data or an empty list if the file doesn't exist.
    """
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                existing_results = json.load(f)
            logging.info(f"Loaded existing results from {results_file}.")
            return existing_results
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in existing results file: {results_file}. Error: {e}. Starting fresh.")
            return []
        except Exception as e:
            logging.error(f"Error loading existing results file: {results_file}. Error: {e}. Starting fresh.")
            return []
    else:
        logging.info(f"No existing results file found at {results_file}. Starting fresh.")
        return []

def process_judged_file(file_path, score_categories, expected_judges, has_jury_in_all_files):
    """
    Processes a single judged JSON file to extract and aggregate scores per judge and jury.

    Args:
        file_path (str): The path to the judged JSON file.
        score_categories (dict): Mapping from short keys to full descriptive names.
        expected_judges (list): List of expected judge keys present in all files.
        has_jury_in_all_files (bool): Indicates if the jury is present in all files.

    Returns:
        dict: Aggregated results for the model, including per-judge and jury scores.
    """
    logging.info(f"Processing file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}. Skipping.")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in file: {file_path}. Error: {e}. Skipping.")
        return None

    if not dataset:
        logging.warning(f"Dataset in file {file_path} is empty. Skipping.")
        return None

    total_entries = len(dataset)
    successful_entries = 0
    failed_entries = 0

    # Initialize model metadata
    model_meta = None

    # Initialize judge names mapping
    judge_names = {}
    first_entry = dataset[0]
    for judge_key in expected_judges:
        judge_data = first_entry.get(judge_key, {})
        judge_name = judge_data.get("Judge Name", judge_key)
        judge_names[judge_key] = judge_name

    if has_jury_in_all_files:
        judge_names['Jury'] = 'Jury'

    # Prepare the list of judges to process
    judges_to_process = expected_judges.copy()
    if has_jury_in_all_files:
        judges_to_process.append('Jury')

    # Initialize per-judge and jury sums and counts
    judge_sums = {}
    judge_counts = {}
    judge_task_sums = {}
    judge_task_counts = {}

    for judge_key in judges_to_process:
        judge_sums[judge_key] = {full_name: 0.0 for full_name in score_categories.values()}
        judge_counts[judge_key] = {full_name: 0 for full_name in score_categories.values()}
        judge_task_sums[judge_key] = defaultdict(float)
        judge_task_counts[judge_key] = defaultdict(int)

    for entry in dataset:
        meta = entry.get("Meta", {})
        task = meta.get("Task")

        # Extract model metadata from the first entry
        if model_meta is None:
            model_meta = {
                "Model Name": meta.get("Model Name"),
                "License": meta.get("License"),
                "Revision": meta.get("Revision"),
                "Precision": meta.get("Precision"),
                "Params": meta.get("Params")
            }

        valid_entry = True

        # Check for missing or invalid scores for all judges and jury
        for judge_key in judges_to_process:
            judge_data = entry.get(judge_key, {})
            scores = judge_data.get("3C3H Scores", {})
            if not scores or any(v is None for v in scores.values()):
                valid_entry = False
                logging.warning(f"Invalid or missing scores for {judge_key} in entry. Skipping this entry.")
                break  # No need to check further if any judge or jury has invalid scores

        if not valid_entry:
            failed_entries += 1
            continue  # Skip processing this entry

        successful_entries += 1

        # Aggregate scores for each judge and jury
        for judge_key in judges_to_process:
            judge_data = entry.get(judge_key, {})
            scores = judge_data.get("3C3H Scores", {})

            # Aggregate 3C3H scores
            for short_key, full_name in score_categories.items():
                value = scores.get(short_key)
                if isinstance(value, (int, float)):
                    judge_sums[judge_key][full_name] += value
                    judge_counts[judge_key][full_name] += 1
                else:
                    logging.warning(f"Invalid value for {short_key} in entry for {judge_key}. Setting to 0.")
                    # Even though the entry is valid, we handle invalid individual scores
                    judge_sums[judge_key][full_name] += 0
                    judge_counts[judge_key][full_name] += 1

            # Aggregate Task Scores
            final_score = scores.get("Final Score")
            if task and isinstance(final_score, (int, float)):
                judge_task_sums[judge_key][task] += final_score
                judge_task_counts[judge_key][task] += 1
            else:
                if not task:
                    logging.warning(f"No 'Task' found in entry's 'Meta'. Skipping task aggregation for {judge_key} in this entry.")
                if not isinstance(final_score, (int, float)):
                    logging.warning(f"Invalid or missing 'Final Score' in entry for {judge_key}. Skipping task aggregation for this entry.")

    # Now compute average scores for each judge and jury
    judge_results = {}
    for judge_key in judges_to_process:
        average_3c3h_scores = {}
        for full_name in score_categories.values():
            if judge_counts[judge_key][full_name] > 0:
                average = judge_sums[judge_key][full_name] / judge_counts[judge_key][full_name]
                average_3c3h_scores[full_name] = round(average, 4)
            else:
                average_3c3h_scores[full_name] = None  # No valid scores

        average_task_scores = {}
        for task, total in judge_task_sums[judge_key].items():
            count = judge_task_counts[judge_key][task]
            if count > 0:
                average = total / count
                average_task_scores[task] = round(average, 4)
            else:
                average_task_scores[task] = None  # No valid scores

        # Retrieve the judge name
        judge_name = judge_names.get(judge_key, judge_key)

        judge_results[f"{judge_name} Scores"] = {
            "3C3H Scores": average_3c3h_scores,
            "Tasks Scores": average_task_scores
        }

    # Calculate success ratio
    if total_entries > 0:
        success_ratio = successful_entries / total_entries
    else:
        success_ratio = 0.0

    # Compile model results with the new structure
    model_results = {
        **judge_results,
        "Meta": {
            "Model Name": model_meta.get("Model Name"),
            "License": model_meta.get("License"),
            "Revision": model_meta.get("Revision"),
            "Precision": model_meta.get("Precision"),
            "Params": model_meta.get("Params"),
            "Total Entries": total_entries,
            "Successful Entries": successful_entries,
            "Failed Entries": failed_entries,
            "Success Ratio": round(success_ratio, 4)
        }
    }

    logging.info(f"Completed processing for model: {model_meta.get('Model Name')}")
    return model_results

def save_results(results_file, results):
    """
    Saves the results to the specified output file.

    Args:
        results_file (str): The path to the results JSON file.
        results (list): The results data to save.
    """
    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        logging.info(f"Results successfully saved to {results_file}")
    except Exception as e:
        logging.error(f"Failed to save results to {results_file}. Error: {e}")

def main():
    setup_logging()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Averaging script for results.')
    parser.add_argument(
        '--answers',
        type=str,
        required=True,
        help='Directory containing the judged JSON answer files.'
    )
    parser.add_argument(
        '--results',
        type=str,
        required=True,
        help='Directory where the aggregated results will be saved.'
    )
    parser.add_argument(
        '--batch_num',
        type=int,
        default=1,
        help='Batch number for naming the results file (default: 1).'
    )
    parser.add_argument(
        '--strategy',
        type=str,
        default='vote',
        help='Strategy to use for jury decision: "average" or "vote".'
    )
    args = parser.parse_args()

    answers_dir = args.answers
    results_dir = args.results
    batch_num = args.batch_num
    strategy = args.strategy

    # Define the score categories mapping
    score_category_names = {
        'Correct': 'Correctness',
        'Complete': 'Completeness',
        'Concise': 'Conciseness',
        'Helpful': 'Helpfulness',
        'Honest': 'Honesty',
        'Harmless': 'Harmlessness',
        'Final Score': '3C3H Score'
    }

    # Retrieve all judged JSON files
    judged_files = get_judged_json_files(answers_dir, suffix="_judged.json")

    if not judged_files:
        logging.info(f"No judged JSON files found in {answers_dir}. Exiting.")
        sys.exit(0)

    # Determine the common judges and jury presence across all files
    judges_per_file = []
    has_jury_in_files = []

    for file_path in judged_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            print("Processing file: ", file_path)
            dataset = json.load(f)
        if not dataset:
            continue  # Skip empty datasets

        # Find an entry that has judge keys
        entry_with_judges = None
        for entry in dataset:
            judge_keys = [key for key in entry.keys() if key.startswith('Judge ')]
            if judge_keys:
                entry_with_judges = entry
                break  # Found an entry with judge keys

        if not entry_with_judges:
            logging.warning(f"No entries with judges found in file {file_path}")
            continue  # Skip this file

        judges_list = [key for key in entry_with_judges.keys() if key.startswith('Judge ')]
        judges_set = set(judges_list)
        judges_per_file.append(judges_set)
        has_jury_in_file = 'Jury' in entry_with_judges
        has_jury_in_files.append(has_jury_in_file)

    if not judges_per_file:
        logging.error("No judges found in any files. Exiting.")
        sys.exit(1)

    # Compute the intersection of judges to find the common judges
    common_judges = set.intersection(*judges_per_file)
    if not common_judges:
        logging.error("No common judges found across files.")
        sys.exit(1)

    expected_judges = list(common_judges)
    has_jury_in_all_files = all(has_jury_in_files)
    logging.info(f"Common judges across all files: {expected_judges}")
    logging.info(f"Jury present in all files: {has_jury_in_all_files}")

    # Load existing results if the file exists
    results_file = os.path.join(results_dir, f"results__strategy_{strategy}.json")
    existing_results = load_existing_results(results_file)

    # Create a dictionary to hold existing model information
    existing_model_info = {}
    for entry in existing_results:
        meta = entry.get('Meta', {})
        model_name = meta.get('Model Name')
        if model_name:
            existing_model_info[model_name] = entry

    # Initialize a list to hold updated results entries
    updated_results_entries = []

    # Process each judged file
    for file_path in judged_files:
        model_results = process_judged_file(file_path, score_category_names, expected_judges, has_jury_in_all_files)
        if model_results:
            model_name = model_results['Meta']['Model Name']
            # Update existing entry or add new one
            existing_model_info[model_name] = model_results
            logging.info(f"Processed model '{model_name}'.")

    # Convert the existing_model_info dictionary back to a list
    updated_results = list(existing_model_info.values())

    # Save the updated results
    save_results(results_file, updated_results)

if __name__ == "__main__":
    main()
