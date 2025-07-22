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
import logging
import argparse
import tempfile
import shutil
from huggingface_hub import snapshot_download
from pathlib import Path

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
    parser = argparse.ArgumentParser(description="Download Hugging Face dataset repository locally and process JSON files.")
    parser.add_argument('--origin_repo', type=str, required=True, help="Hugging Face dataset repository ID (e.g., 'owner/requests-dataset').")
    parser.add_argument('--origin_subdir', type=str, required=True, help="Subdirectory in the dataset (e.g., 'pending').")
    parser.add_argument('--destination_dir', type=str, required=True, help="Local directory to save the JSON files.")
    return parser.parse_args()

def download_dataset(origin_repo, temp_dir, token):
    """
    Downloads the entire dataset repository to a temporary directory.
    """
    try:
        logging.info(f"Starting download of repository '{origin_repo}' to temporary directory.")
        snapshot_download(
            repo_id=origin_repo,
            repo_type="dataset",
            revision="main",  # Change if you need a different branch or tag
            local_dir=temp_dir,
            local_dir_use_symlinks=False,
            use_auth_token=token
        )
        logging.info(f"Successfully downloaded repository '{origin_repo}' to '{temp_dir}'.")
    except Exception as e:
        logging.error(f"Failed to download repository '{origin_repo}': {e}")
        raise

def process_json_files(subdir_path, destination_dir):
    """
    Iterates over subdirectories (ORG) in the specified subdir_path and processes JSON files.
    Copies JSON files to the destination directory, preserving the subdirectory structure.
    Ensures that duplicate files are not copied by checking their existence in the destination.
    """
    try:
        logging.info(f"Processing JSON files in subdirectory '{subdir_path}'.")
        for org_dir in subdir_path.iterdir():
            if org_dir.is_dir():
                org_name = org_dir.name
                logging.info(f"Processing organization: {org_name}")
                for json_file in org_dir.glob("*.json"):
                    if json_file.is_file():
                        relative_path = json_file.relative_to(subdir_path)
                        dest_path = Path(destination_dir) / relative_path

                        if dest_path.exists():
                            logging.info(f"File '{dest_path}' already exists. Skipping copy to avoid duplication.")
                            continue  # Skip copying to prevent duplication

                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(json_file, dest_path)
                        logging.info(f"Copied '{json_file}' to '{dest_path}'.")
        logging.info("Completed processing JSON files.")
    except Exception as e:
        logging.error(f"Error while processing JSON files: {e}")
        raise

def main():
    setup_logging()
    args = parse_arguments()

    origin_repo = args.origin_repo
    origin_subdir = args.origin_subdir
    destination_dir = args.destination_dir

    # Ensure destination directory exists
    os.makedirs(destination_dir, exist_ok=True)

    # Read HF_TOKEN from environment variable
    token = os.environ.get("HF_TOKEN")
    if not token:
        logging.error("HF_TOKEN environment variable is not set. Please set it before running the script.")
        exit(1)
    else:
        logging.info(f"HF_TOKEN is set with length: {len(token)} characters.")

    # Create a temporary directory for downloading the dataset
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Download the dataset repository to the temporary directory
            download_dataset(origin_repo, temp_dir, token)

            # Path to the origin_subdir within the downloaded dataset
            subdir_path = Path(temp_dir) / origin_subdir
            if not subdir_path.exists():
                logging.error(f"The specified subdirectory '{origin_subdir}' does not exist in the repository.")
                exit(1)

            # Process JSON files: copy them to the destination directory without duplications
            process_json_files(subdir_path, destination_dir)

        except Exception as e:
            logging.error(f"An error occurred during synchronization: {e}")
            exit(1)

    logging.info("Synchronization process completed successfully.")

if __name__ == "__main__":
    main()
