#!/bin/bash
#SBATCH --job-name=3c3h
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gpus-per-node=8
#SBATCH --mem=800G
#SBATCH --time=14-00:00:00
#SBATCH --partition=your-partition-name


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

# ==========================
# Set Job ID
# ==========================
# Since this is a SLURM script, we set the JOB_ID to the SLURM_JOB_ID
JOB_ID=$SLURM_JOB_ID

# ==========================
# Configuration Parameters
# ==========================

# Define repository and space  (uncomment if needed)
# TODO: change this to your hub username
# OWNER="your-hfhub-username"
# DESTINATION_REPO="$OWNER/requests-dataset"
# DESTINATION_SPACE="$OWNER/Your-Leaderboard"

# This path is a directory where you save your downloaded models from the hub in the format org1/model_a org1/model_b ... etc
# See ${BASE_DIR}/pipeline/utils/download.sh for more instructions
# TODO: change this to your models folder path
MODELS_DIR="~/models_folder_path"

# Dynamically pick up the directory from which the user ran the script
BASE_DIR="$(pwd)"
# Sanity-check
if [[ ${BASE_DIR##*/} != "3c3h" || ! -f "$BASE_DIR/pipeline/run-pipeline.sh" ]]; then
    echo "Error: This script must be launched from your 3c3h working directory." >&2
    echo "Hint:  cd /path/to/3c3h   # then re-run the script." >&2
    sleep 2      # give log systems time to flush
    exit 1
fi
echo "BASE_DIR resolved to: $BASE_DIR"

DEFAULT_TASK="AraGen-12-2024-dev"

# ==========================
# Command Line Arguments
# ==========================
# Usage: sbatch ~/run-pipeline.sh [OPTIONS]
# OPTIONS:
#   --task TASK           Task name (default: AraGen-12-2024-dev)
#   --model MODEL_NAME    Model name (optional). Can be a single model or a comma-separated list. Supports HuggingFace Hub models (org/model) and proprietary models (e.g., gpt-4o, claude-4-sonnet).
#   --env ENV_NAME        Conda environment name (default: 3c3h)
#   --license LICENSE     License type (default: Open)
#   --revision REVISION   Model revision (default: main)
#   --precision PRECISION Model precision (default: bfloat16)
#   --params PARAMS       Model parameters (default: 0)
#   --status STATUS       Model status (default: RUNNING)
#   --modality MODALITY   Model modality (default: Text)
# Examples:
#   # Process all pending requests with defaults
#   sbatch ./run-pipeline.sh
#   
#   # Process all pending requests with defaults and specific task
#   sbatch ./run-pipeline.sh --task AraGen-03-2025
#
#   # Process specific model with defaults
#   sbatch ./run-pipeline.sh --model inceptionai/jais-family-6p7b-chat
#
#   # Process multiple specific models with defaults (mix of HF and proprietary)
#   sbatch ./run-pipeline.sh --model inceptionai/jais-family-6p7b-chat,gpt-4o,claude-3-sonnet
#
#   # Process specific model with defaults and specific task
#   sbatch ./run-pipeline.sh --model inceptionai/jais-family-6p7b-chat --task AraGen-12-2024
#   
#   # Process specific model with custom parameters
#   sbatch ./run-pipeline.sh --model inceptionai/jais-family-6p7b-chat --params 3B --precision float16
#
#   # Process with custom environment
#   sbatch ./run-pipeline.sh --env my-custom-env --task AraGen-12-2024

# Parse command line arguments
TASK="$DEFAULT_TASK"
MODEL_NAME=""
ENV_NAME="3c3h"
LICENSE="Open"
REVISION=null
PRECISION=null
PARAMS=null
STATUS="RUNNING"
MODALITY="Text"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --task)
            TASK="$2"
            shift 2
            ;;
        --model)
            MODEL_NAME="$2"
            shift 2
            ;;
        --env)
            ENV_NAME="$2"
            shift 2
            ;;
        --license)
            LICENSE="$2"
            shift 2
            ;;
        --revision)
            REVISION="$2"
            shift 2
            ;;
        --precision)
            PRECISION="$2"
            shift 2
            ;;
        --params)
            PARAMS="$2"
            shift 2
            ;;
        --status)
            STATUS="$2"
            shift 2
            ;;
        --modality)
            MODALITY="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "OPTIONS:"
            echo "  --task TASK           Task name (default: $DEFAULT_TASK)"
            echo "  --model MODEL_NAME    Model name (optional). Can be a single model or a comma-separated list. Supports HuggingFace Hub models (org/model) and proprietary models (e.g., gpt-4o, claude-4-sonnet)."
            echo "  --env ENV_NAME        Conda environment name (default: 3c3h)"
            echo "  --license LICENSE     License type (default: Open)"
            echo "  --revision REVISION   Model revision (default: main)"
            echo "  --precision PRECISION Model precision (default: bfloat16)"
            echo "  --params PARAMS       Model parameters (default: 0)"
            echo "  --status STATUS       Model status (default: RUNNING)"
            echo "  --modality MODALITY   Model modality (default: Text)"
            echo ""
            echo "Examples:"
            echo "  # Process all pending requests with defaults"
            echo "  $0"
            echo "  "
            echo "  # Process all pending requests with defaults and specific task"
            echo "  $0 --task AraGen-03-2025"
            echo "  "
            echo "  # Process specific model with defaults"
            echo "  $0 --model inceptionai/jais-family-6p7b-chat"
            echo "  "
            echo "  # Process multiple specific models with defaults (mix of HF and proprietary)"
            echo "  $0 --model inceptionai/jais-family-6p7b-chat,google/gemma-2b,gpt-4o,claude-4-sonnet"
            echo "  "
            echo "  # Process specific model with defaults and specific task"
            echo "  $0 --model inceptionai/jais-family-6p7b-chat --task AraGen-12-2024"
            echo "  "
            echo "  # Process specific model with custom parameters"
            echo "  $0 --model inceptionai/jais-family-6p7b-chat --params 7B --precision float16"
            echo "  "
            echo "  # Process specific model with custom parameters and specific task"
            echo "  $0 --model inceptionai/jais-family-6p7b-chat --params 3B --precision float16 --task AraGen-12-2024"
            echo "  "
            echo "  # Process with custom environment"
            echo "  $0 --env my-custom-env --task AraGen-12-2024"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Use --help or -h for usage information"
            exit 1
            ;;
    esac
done

# Activate the appropriate conda environment
# source ~/miniconda3/etc/profile.d/conda.sh   # Optional: In case your env need to source conda first
conda activate "$ENV_NAME"

# Define the input file
TASKS_DIR="${BASE_DIR}/tasks/"
INPUT_FILE="${TASKS_DIR}/${TASK}.json"

# Directories
OPEN_REQUESTS_DIR="${BASE_DIR}/requests/${TASK}/OpenRequests/"
PROPRIETARY_REQUESTS_DIR="${BASE_DIR}/requests/${TASK}/ProprietaryRequests/"
OUTPUTS_DIR="${BASE_DIR}/answers/${TASK}/"
RESULTS_DIR="${BASE_DIR}/results/${TASK}/"

LOGS_DIR="${BASE_DIR}/logs/${TASK}/"
JOB_LOG_DIR="${LOGS_DIR}/${JOB_ID}/"

# Define python scripts & requirements.txt as constants
GENERATE_OMA="${BASE_DIR}/pipeline/generate-oma.py"
GENERATE_PMA="${BASE_DIR}/pipeline/generate-pma.py"
JUDGING_SCRIPT="${BASE_DIR}/pipeline/jury.py"
AVERAGING_SCRIPT="${BASE_DIR}/pipeline/averaging-to-results.py"

# Define utils (${BASE_DIR}/pipeline/utils/) python scripts as constants
SYNC_REQUESTS_TO_LOCAL="${BASE_DIR}/pipeline/utils/sync_requests_to_local.py"
SYNC_LOCAL_TO_REQUESTS="${BASE_DIR}/pipeline/utils/sync_local_to_requests.py"
SYNC_RESULTS_TO_HUB="${BASE_DIR}/pipeline/utils/sync_results_to_hub.py"

# Define log files
PIPELINE_LOG="${JOB_LOG_DIR}/${JOB_ID}.log"
MODELS_SUCCESS_LOG="${JOB_LOG_DIR}/models_s_${JOB_ID}.txt"
MODELS_FAILURE_LOG="${JOB_LOG_DIR}/models_f_${JOB_ID}.txt"

# =======================
# Initialize Directories
# =======================
mkdir -p "$OPEN_REQUESTS_DIR" \
         "$PROPRIETARY_REQUESTS_DIR" \
         "$OUTPUTS_DIR" \
         "$RESULTS_DIR" \
         "$LOGS_DIR" \
         "$JOB_LOG_DIR"

echo "All required directories are created successfully."

# Redirect all stdout and stderr to the pipeline log file
exec > "$PIPELINE_LOG" 2>&1

# Authenticate to Hugging Face using the token from the file
huggingface-cli login --token $HF_TOKEN

echo "=========================================="
echo "Pipeline start under Job ID: $JOB_ID"
echo "Logs are being written to: $PIPELINE_LOG"
echo "=========================================="

echo "Using conda environment: $ENV_NAME"


# # ====================================================================
# # Synchronize Pending Requests from Hub to Local (uncomment if needed)
# # ====================================================================
# echo "Synchronizing pending requests from Hub to local directory..."
# python -u "$SYNC_REQUESTS_TO_LOCAL" \
#     --origin_repo "$DESTINATION_REPO" \
#     --origin_subdir "pending" \
#     --destination_dir "$OPEN_REQUESTS_DIR"


# ===============================
# Handle Model Argument
# ===============================
if [ -n "$MODEL_NAME" ]; then
    echo "Model name(s) provided: $MODEL_NAME"
    
    # Convert comma-separated string to an array
    IFS=',' read -r -a model_names_array <<< "$MODEL_NAME"

    # Print a summary of the models specified via --model
    echo "Total models specified: ${#model_names_array[@]}"
    echo "Models to process:"
    for model_item in "${model_names_array[@]}"; do
        echo " - $model_item"
    done

    # Initialize an array to hold the paths of the generated request files
    all_eval_request_files=()

    for current_model_name in "${model_names_array[@]}"; do
        echo "----------------------------------------"
        echo "Handling model: $current_model_name"
        
        # Auto-detect model type based on presence of "/"
        if [[ "$current_model_name" == *"/"* ]]; then
            # Model contains "/" - it's a HuggingFace Hub model
            DETECTED_LICENSE="Open"
            echo "Detected as HuggingFace Hub model (Open source)"
        else
            # Model doesn't contain "/" - it's a proprietary model
            DETECTED_LICENSE="Proprietary"
            echo "Detected as proprietary model"
        fi
        
        # Determine the request directory based on detected license
        if [ "$DETECTED_LICENSE" == "Proprietary" ]; then
            REQUEST_DIR="$PROPRIETARY_REQUESTS_DIR"
        else
            REQUEST_DIR="$OPEN_REQUESTS_DIR"
        fi
        
        # Extract organization and model name
        if [[ "$current_model_name" == *"/"* ]]; then
            # HF Hub model: org/model format
            ORG_NAME=$(echo "$current_model_name" | cut -d'/' -f1)
            MODEL_ID=$(echo "$current_model_name" | cut -d'/' -f2)
        else
            # Proprietary model: just model name, determine org based on model name
            MODEL_NAME_LOWER=$(echo "$current_model_name" | tr '[:upper:]' '[:lower:]')
            MODEL_ID="$current_model_name"
            
            if [[ "$MODEL_NAME_LOWER" == *"gpt"* || "$MODEL_NAME_LOWER" == o* ]]; then
                ORG_NAME="openai"
            elif [[ "$MODEL_NAME_LOWER" == *"claude"* ]]; then
                ORG_NAME="anthropic"
            elif [[ "$MODEL_NAME_LOWER" == *"gemini"* ]]; then
                ORG_NAME="google"
            elif [[ "$MODEL_NAME_LOWER" == *"jais"* || "$MODEL_NAME_LOWER" == *"k2"* || "$MODEL_NAME_LOWER" == *"nanda"* ]]; then
                ORG_NAME="inception"
            elif [[ "$MODEL_NAME_LOWER" == *"deepseek"* ]]; then
                ORG_NAME="deepseek"
            elif [[ "$MODEL_NAME_LOWER" == *"mistral"* ]]; then
                ORG_NAME="mistral"
            elif [[ "$MODEL_NAME_LOWER" == *"grok"* ]]; then
                ORG_NAME="xai"
            else
                echo "Unknown proprietary model: $current_model_name"
                ORG_NAME="unknown"
            fi
        fi
        
        # Create organization directory if it doesn't exist
        ORG_DIR="${REQUEST_DIR}/${ORG_NAME}"
        mkdir -p "$ORG_DIR"
        
        # Create the request file name
        REQUEST_FILE="${ORG_DIR}/${MODEL_ID}_eval_request_${REVISION}_${PRECISION}.json"
        
        # Check if request file already exists and check its status
        if [ -f "$REQUEST_FILE" ]; then
            EXISTING_STATUS=$(jq -r '.status' "$REQUEST_FILE")
            echo "Request file already exists: $REQUEST_FILE"
            echo "Existing status: $EXISTING_STATUS"
            
            if [ "$EXISTING_STATUS" == "FINISHED" ]; then
                echo "Model $current_model_name has already been processed successfully. The script will skip it if its status remains 'FINISHED'."
            else
                echo "Model $current_model_name has status '$EXISTING_STATUS'. Will proceed with processing."
            fi
        else
            echo "Creating new request file for model: $current_model_name"
            # Create the request file
            cat > "$REQUEST_FILE" << EOF
{
  "model_name": "$current_model_name",
  "license": "$DETECTED_LICENSE",
  "revision": "$REVISION",
  "precision": "$PRECISION",
  "params": "$PARAMS",
  "status": "$STATUS",
  "modality": "$MODALITY"
}
EOF
            echo "Request file created: $REQUEST_FILE"
        fi
        
        # Add the request file to the list
        all_eval_request_files+=("$REQUEST_FILE")
    done    
    echo "----------------------------------------"

else
    echo "No model name provided, processing all requests in directories..."
fi

# ===============================
# Model Processing Phase
# ===============================
if [ -z "$MODEL_NAME" ]; then
    # Find all eval_request JSON files in the OPEN_REQUESTS_DIR
    readarray -t open_eval_request_files < <(find "$OPEN_REQUESTS_DIR" -type f -name "*.json")
    readarray -t proprietary_eval_request_files < <(find "$PROPRIETARY_REQUESTS_DIR" -type f -name "*.json")
    # Merge both arrays into all_eval_request_files
    all_eval_request_files=("${open_eval_request_files[@]}" "${proprietary_eval_request_files[@]}")
fi

# Reset status of RUNNING requests back to PENDING
echo "Checking and resetting status of RUNNING requests to PENDING..."
for eval_request_file in "${all_eval_request_files[@]}"; do
    status=$(jq -r '.status' "$eval_request_file")
    if [[ "$status" == "RUNNING" ]]; then
        jq '.status = "PENDING"' "$eval_request_file" > "${eval_request_file}.tmp" && mv "${eval_request_file}.tmp" "$eval_request_file"
        echo "Updated status of $eval_request_file to PENDING."
    fi
done
echo "Status reset completed."

# Initialize an array to hold only PENDING requests
pending_eval_request_files=()

# Populate pending_eval_request_files with only those requests whose status is "PENDING".
for eval_request_file in "${all_eval_request_files[@]}"; do
    status=$(jq -r '.status' "$eval_request_file")

    if [[ "$status" == "PENDING" ]]; then
        pending_eval_request_files+=("$eval_request_file")
    fi
done


# Initialize counters for tracking progress and results
PROCESSING_COUNT=0
TOTAL_MODELS=${#pending_eval_request_files[@]}
SUCCESS_COUNT=0     # Counter for successful model processing
FAILURE_COUNT=0     # Counter for failed model processing

# Initialize log files for successes and failures
> "$MODELS_SUCCESS_LOG"  # Truncate/Create the success log file
> "$MODELS_FAILURE_LOG"  # Truncate/Create the failure log file

echo "========================================"
echo "Starting Model Processing Phase"
echo "Total Models to Process: $TOTAL_MODELS"
echo "Model Names to be processed:"
for eval_request_file in "${pending_eval_request_files[@]}"; do
    model_name=$(jq -r '.model_name' "$eval_request_file")
    echo "$model_name"
done
echo "========================================"

# Get start time
START_TIME=$(date +%s)

# Iterate over each eval_request file
for EVAL_REQUEST_FILE in "${pending_eval_request_files[@]}"
do 
    echo "----------------------------------------"
    echo "Processing Eval Request File: $EVAL_REQUEST_FILE"
    echo "----------------------------------------"

    # Read model details from the eval_request file
    MODEL_NAME=$(jq -r '.model_name' "$EVAL_REQUEST_FILE")
    LICENSE=$(jq -r '.license' "$EVAL_REQUEST_FILE")
    MODEL_REVISION=$(jq -r '.revision' "$EVAL_REQUEST_FILE")
    MODEL_PRECISION=$(jq -r '.precision' "$EVAL_REQUEST_FILE")
    MODEL_STATUS=$(jq -r '.status' "$EVAL_REQUEST_FILE")
    MODEL_SIZE=$(jq -r '.params' "$EVAL_REQUEST_FILE")
    MODALITY=$(jq -r '.modality' "$EVAL_REQUEST_FILE")
    # MODALITY="Text" # =$(jq -r '.modality' "$EVAL_REQUEST_FILE") # ["Text", "Text+Vision"]

    # Proceed only if the status is not 'FINISHED'
    if [ "$MODEL_STATUS" == "FINISHED" ]; then
        echo "Model $MODEL_NAME has been already processed. Skipping."
        continue
    fi

    echo "Model Name: $MODEL_NAME"
    echo "Model Revision: $MODEL_REVISION"
    echo "Model Precision: $MODEL_PRECISION"
    echo "Model Status: $MODEL_STATUS"
    echo "Model License: $LICENSE"
    echo "Model Size: $MODEL_SIZE"
    echo "Modality: $MODALITY"

    # Check License if not Proprietary
    if [ "$LICENSE" != "Proprietary" ]; then
        # Extract org and model ID from MODEL_NAME
        ORG=$(echo "$MODEL_NAME" | cut -d'/' -f1)
        MODEL_ID=$(echo "$MODEL_NAME" | cut -d'/' -f2)
        MODEL_PATH="${MODELS_DIR}/${ORG}/${MODEL_ID}"

        # Check if the model exists locally
        if [ ! -d "$MODEL_PATH" ]; then
            echo "Model not found locally. Downloading model: $MODEL_NAME"
            # Create the directory for the model
            mkdir -p "$MODEL_PATH"

            # Download the model using huggingface-cli
            start_time=$(date +%s)

            # Run the download command
            huggingface-cli download "$MODEL_NAME" --repo-type model --revision "$MODEL_REVISION" --local-dir "$MODEL_PATH"

            end_time=$(date +%s)
            time_taken=$((end_time - start_time))

            echo "Model: $MODEL_NAME downloaded | Time taken: ${time_taken}s"
        else
            echo "Model already found locally"
        fi
    else
        # For Proprietary Models
        # Determine the provider based on the model name
        # MODEL_NAME_LOWER is already defined above for JAIS detection

        if [[ "$MODEL_NAME_LOWER" == *"gpt"* || "$MODEL_NAME_LOWER" == o* ]]; then
            ORG="openai"
        elif [[ "$MODEL_NAME_LOWER" == *"claude"* ]]; then
            ORG="anthropic"
        elif [[ "$MODEL_NAME_LOWER" == *"gemini"* ]]; then
            ORG="google"
        elif [[ "$MODEL_NAME_LOWER" == *"jais"* || "$MODEL_NAME_LOWER" == *"k2"* || "$MODEL_NAME_LOWER" == *"nanda"* ]]; then
            ORG="inception"
        elif [[ "$MODEL_NAME_LOWER" == *"deepseek"* ]]; then
            ORG="deepseek"
        elif [[ "$MODEL_NAME_LOWER" == *"mistral"* ]]; then
            ORG="mistral"
        elif [[ "$MODEL_NAME_LOWER" == *"grok"* ]]; then
            ORG="xai"
        else
            echo "Unknown proprietary model: $MODEL_NAME"
            ORG="unknown"
        fi
    fi

    # -------------------------------
    # Generate Model Answers
    # -------------------------------
    echo "Generating answers for model: $MODEL_NAME"

    # Update status to 'RUNNING' in the eval_request file
    jq '.status = "RUNNING"' "$EVAL_REQUEST_FILE" > "${EVAL_REQUEST_FILE}.tmp" && mv "${EVAL_REQUEST_FILE}.tmp" "$EVAL_REQUEST_FILE"
    
    # Check Model Type either Open or Proprietary
    if [ "$LICENSE" != "Proprietary" ]; then
        python -u "$GENERATE_OMA" \
            --model_path "$MODEL_PATH" \
            --license "$LICENSE" \
            --revision "$MODEL_REVISION" \
            --precision "$MODEL_PRECISION" \
            --params "$MODEL_SIZE" \
            --modality "$MODALITY" \
            --input_file "$INPUT_FILE" \
            --output "$OUTPUTS_DIR" \
            --batch "$TASK"
    else
        python -u "$GENERATE_PMA" \
            --model_name "$MODEL_NAME" \
            --input_file "$INPUT_FILE" \
            --output "$OUTPUTS_DIR" \
            --batch "$TASK"
    fi

    # Capture the exit status of the Generate Answers script
    GEN_EXIT_STATUS=$?

    if [ $GEN_EXIT_STATUS -eq 0 ]; then
        echo "SUCCESS: Answers generated for model $MODEL_NAME."
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))  # Increment success counter
        echo "$MODEL_NAME" >> "$MODELS_SUCCESS_LOG"  # Log the successful model
        # Update status to 'FINISHED' in the eval_request file
        jq '.status = "FINISHED"' "$EVAL_REQUEST_FILE" > "${EVAL_REQUEST_FILE}.tmp" && mv "${EVAL_REQUEST_FILE}.tmp" "$EVAL_REQUEST_FILE"
    else
        echo "ERROR: Failed to generate answers for model $MODEL_NAME."
        echo "$MODEL_NAME" >> "$MODELS_FAILURE_LOG"  # Log the failed model
        FAILURE_COUNT=$((FAILURE_COUNT + 1))  # Increment failure counter
        # Update status to 'FAILED' in the eval_request file
        jq '.status = "FAILED"' "$EVAL_REQUEST_FILE" > "${EVAL_REQUEST_FILE}.tmp" && mv "${EVAL_REQUEST_FILE}.tmp" "$EVAL_REQUEST_FILE"
        # Skip judging and averaging for this model and continue to next model
        continue
    fi
    
    # Increment the processing counter
    PROCESSING_COUNT=$((PROCESSING_COUNT + 1))
    echo "Progress: $PROCESSING_COUNT/$TOTAL_MODELS models processed."


    # -------------------------------
    # Judging Model Answers
    # -------------------------------
    python -u "$JUDGING_SCRIPT" \
        --answers "$OUTPUTS_DIR" \
        --judge-list "claude-3.5-sonnet" \
        --strategy "average"

    # Capture the exit status of the Judging script
    JUDGE_EXIT_STATUS=$?

    if [ $JUDGE_EXIT_STATUS -eq 0 ]; then
        echo "SUCCESS: Judging completed"
    else
        echo "ERROR: Judging failed"
    fi
done


# ---------------------------------------------------------------------
# Re-Running the "Judging Model Answers" in case of missed unjudged files
# ---------------------------------------------------------------------
python -u "$JUDGING_SCRIPT" \
    --answers "$OUTPUTS_DIR" \
    --judge-list "claude-3.5-sonnet" \
    --strategy "average"

# Capture the exit status of the Judging script
JUDGE_EXIT_STATUS=$?

if [ $JUDGE_EXIT_STATUS -eq 0 ]; then
    echo "SUCCESS: Judging completed"
else
    echo "ERROR: Judging failed"
fi


# -------------------------------
# Averaging Phase
# -------------------------------
python -u "$AVERAGING_SCRIPT" \
    --answers "$OUTPUTS_DIR" \
    --results "$RESULTS_DIR"

# Capture the exit status of the Averaging script
AVERAGING_EXIT_STATUS=$?

if [ $AVERAGING_EXIT_STATUS -eq 0 ]; then
    echo "SUCCESS: Averaging completed."
else
    echo "ERROR: Averaging failed."
fi


# ===========================
# Summary of Model Processing
# ===========================
echo "========================================"
echo "All models have been processed."
echo "========================================"
echo "========================================"
echo "Model Processing Phase Summary"
echo "========================================"
echo "Total Models Processed: $TOTAL_MODELS"
echo "Successful Models: $SUCCESS_COUNT"
echo "Failed Models: $FAILURE_COUNT"
echo "========================================"


# List the successful and failed models
if [ $SUCCESS_COUNT -gt 0 ]; then
    echo "List of Successful Models:" | tee -a "$PIPELINE_LOG"
    cat "$MODELS_SUCCESS_LOG"
    # cat "$MODELS_SUCCESS_LOG" | awk '{print " - " $0}' | tee -a "$PIPELINE_LOG"
fi

if [ $FAILURE_COUNT -gt 0 ]; then
    echo "List of Failed Models:" | tee -a "$PIPELINE_LOG"
    cat "$MODELS_FAILURE_LOG"
    # cat "$MODELS_FAILURE_LOG" | awk '{print " - " $0}' | tee -a "$PIPELINE_LOG"
fi


# # ====================================================================
# # Synchronize Pending Requests from Hub to Local (uncomment if needed)
# # ====================================================================
# echo "Synchronizing pending requests from Hub to local directory..."
# python -u "$SYNC_REQUESTS_TO_LOCAL" \
#     --origin_repo "$DESTINATION_REPO" \
#     --origin_subdir "pending" \
#     --destination_dir "$OPEN_REQUESTS_DIR"

# # ============================================================
# # Synchronize Local Requests Back to Hub (uncomment if needed)
# # ============================================================
# echo "Synchronizing local requests back to Hub dataset..."
# python -u "$SYNC_LOCAL_TO_REQUESTS" \
#     --origin_dir "$OPEN_REQUESTS_DIR" \
#     --destination_repo "$DESTINATION_REPO" \
#     --status_field "status" \
#     --categories "PENDING" "FINISHED" "FAILED"

# # =====================================================
# # Synchronize Results Back to Hub (uncomment if needed)
# # =====================================================
# echo "Synchronizing results back to Hub..."
# python -u "$SYNC_RESULTS_TO_HUB" \
#     --origin_dir "$RESULTS_DIR" \
#     --destination_space "$DESTINATION_SPACE" \
#     --destination_path "assets/results/aragen_v2_results.json"


# ===============================
# Clean Up
# ===============================
echo "================================================"
echo "Pipeline under Job ID ($JOB_ID) Completed."
echo "All logs are available in: $PIPELINE_LOG"
echo "================================================"

# Get end time
END_TIME=$(date +%s)
# Calculate time taken
TIME_TAKEN=$((END_TIME - START_TIME))

# Log the model and time taken to the log file
echo "$(date +'%Y-%m-%d %H:%M:%S') Time taken to run the pipeline: ${TIME_TAKEN}s"
