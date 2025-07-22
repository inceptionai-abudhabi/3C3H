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

import os
import json
import logging
import argparse
import pandas as pd
from datetime import datetime
from huggingface_hub import HfApi

def setup_logging():
    """
    Configures logging to output to the console (stdout).
    This ensures that logs are captured by the main pipeline's log file.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Create a stream handler to output logs to stdout
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    
    # Define the logging format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    # Add the handler to the logger
    logger.addHandler(handler)

def parse_arguments():
    """
    Parses command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Aggregate and sync evaluation results to Hugging Face Space.")
    parser.add_argument('--origin_dir', type=str, required=True, help="Local directory containing result JSON files.")
    parser.add_argument('--destination_space', type=str, required=True, help="Hugging Face Space repository ID (e.g., 'owner/SpaceName').")
    parser.add_argument('--destination_path', type=str, required=True, help="Path within the Space to save 'results.json' (e.g., 'assets/results/results.json').")
    return parser.parse_args()

def aggregate_results(origin_dir):
    """
    Aggregates all JSON results from the origin directory into a single flat list.
    Ensures that the final structure is a list of dictionaries.
    We explicitly skip any 'results.json' files to prevent re-aggregation of previously aggregated data.
    """
    aggregated_data = []
    try:
        # Iterate through all JSON files in the origin directory
        for root, _, files in os.walk(origin_dir):
            for file in files:
                # Skip any previously generated aggregated results.json file
                if file == "results.json":
                    logging.info(f"Skipping '{file}' to avoid duplication.")
                    continue
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    logging.info(f"Processing file: {file_path}")
                    with open(file_path, 'r') as f:
                        try:
                            result = json.load(f)
                            if isinstance(result, list):
                                # If the JSON file contains a list, extend the aggregated_data
                                aggregated_data.extend(result)
                                logging.info(f"Extended aggregated_data with {len(result)} entries from '{file}'.")
                            elif isinstance(result, dict):
                                # If the JSON file contains a single dictionary, append it
                                aggregated_data.append(result)
                                logging.info(f"Appended 1 entry from '{file}'.")
                            else:
                                logging.warning(f"Unexpected JSON structure in file '{file}'. Expected list or dict. Skipping.")
                        except json.JSONDecodeError:
                            logging.error(f"Invalid JSON format in file '{file}'. Skipping.")
                            continue
        logging.info(f"Aggregated a total of {len(aggregated_data)} entries from '{origin_dir}'.")
        return aggregated_data
    except Exception as e:
        logging.error(f"Error during aggregation of results: {str(e)}")
        return aggregated_data

def sync_results_to_space(aggregated_data, destination_space, destination_path):
    """
    Uploads the aggregated results.json to the specified Hugging Face Space.
    Adds a timestamp field to ensure that the commit is always detected as changed.
    """
    try:
        api = HfApi()
        
        # Add a dummy timestamp field to ensure a change on every run
        # If aggregated_data is a list, we can add a dict at the end or transform it to a dict containing data.
        # To keep it consistent as a list, we'll just append a special marker dict.
        aggregated_data.append({"_last_sync_timestamp": datetime.utcnow().isoformat()})
        
        # Convert aggregated data to JSON
        aggregated_json = json.dumps(aggregated_data, indent=4)
        
        # Save to a temporary file
        temp_results_path = "/tmp/results.json"
        with open(temp_results_path, 'w') as f:
            f.write(aggregated_json)
        logging.info(f"Aggregated results saved to temporary file '{temp_results_path}'.")
        
        # Attempt upload
        try:
            api.upload_file(
                path_or_fileobj=temp_results_path,
                path_in_repo=destination_path,
                repo_id=destination_space,
                repo_type="space",
                commit_message="Update results.json with latest aggregated results.",
                token=os.environ.get("HF_TOKEN")
            )
            logging.info(f"Successfully committed changes to '{destination_path}' in Space '{destination_space}'.")
        except Exception as e:
            logging.error(f"Error uploading results to Space '{destination_space}': {e}")
        
        # Remove the temporary file
        os.remove(temp_results_path)
        logging.info(f"Temporary file '{temp_results_path}' removed.")
    
    except Exception as e:
        logging.error(f"Error during syncing results to Hub Space: {str(e)}")

def main():
    setup_logging()
    args = parse_arguments()
    
    # Ensure origin directory exists
    if not os.path.isdir(args.origin_dir):
        logging.error(f"Origin directory '{args.origin_dir}' does not exist.")
        return
    
    logging.info("Starting aggregation of evaluation results.")
    aggregated_data = aggregate_results(args.origin_dir)
    
    if not aggregated_data:
        # If aggregated_data is empty, we still want to commit (to show sync)
        aggregated_data = []
        logging.warning("No valid results found to sync. Will still commit timestamp to ensure visibility.")
    
    logging.info("Starting synchronization of aggregated results to Hugging Face Space.")
    sync_results_to_space(aggregated_data, args.destination_space, args.destination_path)
    logging.info("Synchronization of results completed.")

if __name__ == "__main__":
    main()
