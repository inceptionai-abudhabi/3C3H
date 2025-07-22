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
from pathlib import Path
from huggingface_hub import HfApi
import subprocess

def setup_logging():
    """
    Configures logging to output to the console (stdout).
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove all existing handlers to prevent duplicate logs
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

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
    parser = argparse.ArgumentParser(description="Sync local requests to Hugging Face Hub dataset with categorization.")
    parser.add_argument('--origin_dir', type=str, required=True, help="Local directory containing submission JSON files.")
    parser.add_argument('--destination_repo', type=str, required=True, help="Hugging Face dataset repository ID (e.g., 'owner/requests-dataset').")
    parser.add_argument('--status_field', type=str, default='status', help="JSON field that indicates the submission status.")
    parser.add_argument('--categories', type=str, nargs='+', default=["PENDING", "FINISHED", "FAILED"],
                        help="List of status categories to map to subdirectories.")
    parser.add_argument('--hf_token', type=str, default=None, help="Optional: Hugging Face authentication token. If not provided, it will be read from the HF_TOKEN environment variable.")
    return parser.parse_args()

def categorize_submission(status, categories):
    """
    Map the status to the corresponding subdirectory.
    """
    status = status.upper()
    mapping = {
        "PENDING": "pending",
        "FINISHED": "finished",
        "FAILED": "failed"
    }
    return mapping.get(status, "pending")

def get_existing_files(api, destination_repo):
    """
    Retrieves a set of existing file paths in the destination repository.
    """
    try:
        logging.info(f"Fetching existing files from repository '{destination_repo}'.")
        existing_files = set(api.list_repo_files(repo_id=destination_repo, repo_type="dataset"))
        logging.info(f"Retrieved {len(existing_files)} existing file(s) from the repository.")
        return existing_files
    except Exception as e:
        logging.error(f"Error fetching repository files: {e}")
        return set()

def delete_file_via_cli(repo_id, file_path, token):
    """
    Deletes a file from a Hugging Face repository using the huggingface-cli via subprocess.
    """
    try:
        logging.info(f"Attempting to delete '{file_path}' from repository '{repo_id}'.")

        # Construct the command without --token
        cmd = [
            'huggingface-cli',
            'repo-files',
            repo_id,
            'delete',
            file_path,
            '--repo-type',
            'dataset'
        ]

        # Set the environment with the token
        env = os.environ.copy()
        env['HF_TOKEN_2'] = token

        # Execute the command
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)

        # Check for success message in stdout
        if "Files correctly deleted from repo." in result.stdout or "Successfully deleted" in result.stdout:
            logging.info(f"Successfully deleted '{file_path}' from repository '{repo_id}'.")
            return True
        else:
            logging.error(f"Failed to delete '{file_path}' from repository '{repo_id}'. Output: {result.stdout}")
            return False

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to delete '{file_path}' from repository '{repo_id}'. Error: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        logging.error("huggingface-cli is not installed or not found in PATH.")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while deleting '{file_path}': {e}")
        return False

def sync_local_requests_to_hub(origin_dir, destination_repo, status_field, categories, token):
    """
    Synchronizes local JSON submission files to the Hugging Face Hub dataset repository,
    categorizing them based on their status. This method ensures that the Hub repository
    exactly mirrors the local origin_dir by deleting existing files and repopulating
    based on the current local files.
    """
    api = HfApi()

    # Get the set of existing files on the Hub
    existing_files = get_existing_files(api, destination_repo)

    origin_path = Path(origin_dir)
    if not origin_path.is_dir():
        logging.error(f"Origin directory '{origin_dir}' does not exist or is not a directory.")
        return

    # Normalize category names to lowercase for consistent path handling
    categories_lower = [category.lower() for category in categories]

    # Traverse the origin directory recursively for JSON files
    logging.info(f"Processing JSON files from origin directory '{origin_dir}'.")
    for json_file in origin_path.rglob("*.json"):
        relative_path = json_file.relative_to(origin_path)
        
        # Extract ORG and filename from the relative path
        try:
            org, filename = relative_path.parts[:2]
        except ValueError:
            logging.warning(f"File '{relative_path}' does not follow 'ORG/filename.json' structure. Skipping.")
            continue

        # Read the submission file to determine its status
        try:
            with json_file.open('r', encoding='utf-8') as f:
                submission = json.load(f)
                status = submission.get(status_field, "PENDING")
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON format in file '{relative_path}'. Skipping.")
            continue
        except Exception as e:
            logging.error(f"Error reading file '{relative_path}': {e}. Skipping.")
            continue

        target_subdir = categorize_submission(status, categories)

        # Ensure the target subdirectory is valid
        if target_subdir.upper() not in categories:
            logging.warning(f"Status '{status}' in file '{relative_path}' is not in categories {categories}. Assigning to 'pending'.")
            target_subdir = "pending"

        # Define the target path in the repository
        hub_file_path = f"{target_subdir}/{org}/{filename}"

        # Upload the file to the target subdirectory
        try:
            logging.info(f"Uploading '{hub_file_path}' to repository '{destination_repo}'.")
            api.upload_file(
                path_or_fileobj=str(json_file),
                path_in_repo=hub_file_path,
                repo_id=destination_repo,
                repo_type="dataset",
                commit_message=f"Sync submission '{filename}' to '{target_subdir}/{org}/'",
                token=token
            )
            logging.info(f"Successfully uploaded '{hub_file_path}' to Hub.")
            existing_files.add(hub_file_path)  # Update the existing_files set
        except Exception as e:
            logging.error(f"Failed to upload '{hub_file_path}' to Hub: {e}.")
            continue

        # Identify all possible existing paths for this file across all categories
        # Exclude the target_subdir to prevent immediate deletion after upload
        other_subdirs = [subdir for subdir in categories_lower if subdir != target_subdir]
        for subdir in other_subdirs:
            other_hub_file_path = f"{subdir}/{org}/{filename}"
            if other_hub_file_path in existing_files:
                # Delete the old file from the previous subfolder using huggingface-cli via subprocess
                success = delete_file_via_cli(
                    repo_id=destination_repo,
                    file_path=other_hub_file_path,
                    token=token
                )
                if success:
                    existing_files.remove(other_hub_file_path)  # Update the existing_files set

    logging.info("Completed syncing local requests to Hub dataset.")

def main():
    setup_logging()
    args = parse_arguments()

    # Determine the token to use
    if args.hf_token:
        hf_token = args.hf_token
        logging.info("Using Hugging Face token provided via command-line argument.")
    else:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            logging.error("Hugging Face token not provided via --hf_token and HF_TOKEN environment variable is not set. Exiting.")
            return
        logging.info("Using Hugging Face token from HF_TOKEN environment variable.")

    # Extract arguments
    origin_dir = args.origin_dir
    destination_repo = args.destination_repo
    status_field = args.status_field
    categories = args.categories

    logging.info("Starting synchronization of local requests to Hub dataset.")
    sync_local_requests_to_hub(origin_dir, destination_repo, status_field, categories, hf_token)
    logging.info("Synchronization process completed.")

if __name__ == "__main__":
    main()
