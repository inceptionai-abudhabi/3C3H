#!/bin/bash

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

# Define the list of models
models_list=(
    "inceptionai/jais-family-6p7b"
    "inceptionai/jais-family-6p7b-chat"
)

BASE_DIR="your_home_dir"

# Authenticate to Hugging Face using the token from the file
huggingface-cli login --token "$HF_TOKEN"

# Loop over the models and run the command for each one
for model in "${models_list[@]}"
do
    echo "=========================================="
    echo "Starting process for model: $model"
    echo "=========================================="
    
    # Extract org and model id (m_id) by splitting the model string
    org=$(echo "$model" | cut -d'/' -f1)
    m_id=$(echo "$model" | cut -d'/' -f2)
    
    # The local directory where the model should be stored
    local_dir="$BASE_DIR/models/hf/$org/$m_id"

    # Record the start time
    start_time=$(date +%s)
    
    # Check if the model directory already exists
    if [ -d "$local_dir" ]; then
        echo "Local path found: $local_dir"
        echo "Attempting to load the model locally to verify integrity..."
        
        # Attempt to load the model locally via a Python check
        if python <<END
import sys
try:
    from transformers import AutoModel
    model = AutoModel.from_pretrained("$local_dir", local_files_only=True)
    sys.exit(0)
except Exception as e:
    sys.exit(1)
END
        then
            echo "Model loaded successfully from local path. No download needed."
        else
            echo "Model failed to load from local path. Removing path and downloading again..."
            rm -rf "$local_dir"
            huggingface-cli download "$model" --repo-type model --local-dir "$local_dir"
        fi
    else
        echo "Local path not found. Downloading the model for the first time..."
        huggingface-cli download "$model" --repo-type model --local-dir "$local_dir"
    fi
    
    # Record the end time
    end_time=$(date +%s)
    # Calculate time taken for this process
    time_taken=$((end_time - start_time))

    echo "=========================================="
    echo "Finished processing: $model"
    echo "Time taken: ${time_taken}s"
    echo "=========================================="
    echo ""
done