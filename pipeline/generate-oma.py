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

"""
This script generates answers to the passed dataset for Open Models from the Hugging Face Hub.
"""

import os
import time
import json
import torch
import argparse
import gc
import copy
import subprocess
from pathlib import Path

# ---------------- For Text Models ----------------
from transformers import AutoTokenizer, AutoModelForCausalLM

# ---------------- For Vision Models ----------------
from transformers import AutoProcessor, AutoModelForVision2Seq #, Gemma3ForConditionalGeneration 
from huggingface_hub import snapshot_download

# ---------------- Utility Functions ----------------
def get_free_gpu_id(threshold_mb: int = 1000) -> int:
    """
    Return the index of an (almost) idle GPU.

    A GPU is considered “free” if its memory-used value reported by nvidia-smi
    is below `threshold_mb`.  If all GPUs are above the threshold, the GPU with
    the *least* memory used is returned.  If detection fails, default to 0.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        gpu_stats = [
            tuple(map(int, line.strip().split(",")))
            for line in result.stdout.strip().splitlines()
        ]  # -> [(idx, used_mb), …]

        # Prefer the first GPU under the threshold
        for idx, used in gpu_stats:
            if used < threshold_mb:
                print(f"✅  GPU {idx} is free enough ({used} MiB used).")
                return idx

        # Otherwise pick the least busy one
        idx, used = min(gpu_stats, key=lambda x: x[1])
        print(
            f"⚠️  All GPUs busy – taking least-used GPU {idx} "
            f"({used} MiB used)."
        )
        return idx
    except FileNotFoundError:
        print("⚠️  'nvidia-smi' not found – assuming single-GPU system (GPU 0).")
        return 0
    except Exception as e:
        print(f"⚠️  Could not query GPU usage ({e}). Falling back to GPU 0.")
        return 0

def extract_model_name(model_path):
    """
    Extracts a clean model name from the given model path by taking the last two components.
    Returns (org, model_id, raw_model_name).
    """
    path_parts = model_path.strip('/').split('/')
    if len(path_parts) < 2:
        print(f"Error: The model_path '{model_path}' does not have enough components to extract model_name.")
        exit(1)
    org, model_id = path_parts[-2:]
    raw_model_name = f"{org}/{model_id}"
    return org, model_id, raw_model_name

def get_model_folder_size(model_path):
    """
    Calculates the total size (in bytes) of the model directory.
    """
    total_size = 0
    for dirpath, _, filenames in os.walk(model_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    return total_size

def get_precision_bits(precision):
    """
    Determines the number of bits per parameter based on the specified precision.
    """
    precision = precision.lower()
    if precision in ['float32', 'fp32']:
        return 32
    elif precision in ['float16', 'fp16']:
        return 16
    elif precision in ['bfloat16', 'bf16']:
        return 16  # bfloat16 uses 16 bits
    elif precision in ['int8']:
        return 8
    else:
        return 32  # Default to 32 bits

def estimate_model_parameters_by_size(total_size_bytes, bits_per_param):
    """
    Estimates the total number of parameters in the model based on folder size and precision.
    """
    total_size_gb = total_size_bytes / (1024 ** 3)
    if bits_per_param == 8:
        total_params = total_size_gb * 1e9
    elif bits_per_param == 16:
        total_params = (total_size_gb / 2) * 1e9
    elif bits_per_param == 32:
        total_params = (total_size_gb / 4) * 1e9
    else:
        bytes_per_param = bits_per_param / 8
        total_params = total_size_bytes / bytes_per_param
    return int(total_params)

# ---------------- Generation Functions ----------------

def generate_text_answer(model, tokenizer, messages, use_chat_template=True, max_length=2048):
    """
    Generates an answer using a text-only model.
    If the tokenizer supports a chat template, it is used for formatting.
    """
    try:
        if use_chat_template and hasattr(tokenizer, 'apply_chat_template'):
            tokenized = tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
                return_token_type_ids=False # Only for JAIS+
            )
            if isinstance(tokenized, dict):
                input_ids = tokenized['input_ids'].to(model.device)
            else:
                input_ids = tokenized.to(model.device)
        else:
            conversation = "\n".join([msg["content"] for msg in messages])
            tokenized = tokenizer(conversation, return_tensors="pt")
            input_ids = tokenized['input_ids'].to(model.device)
    except Exception as e:
        print(f"Error during tokenization: {e}")
        if use_chat_template:
            print("Retrying without chat template.")
            return generate_text_answer(model, tokenizer, messages, use_chat_template=False, max_length=max_length)
        else:
            return "ERROR"
    
    input_len = input_ids.shape[-1]
    try:
        with torch.no_grad():
            outputs = model.generate(
                input_ids,
                max_length=input_len + max_length,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=False,
                num_return_sequences=1
            )
    except Exception as e:
        print(f"Error during generation: {e}")
        return "ERROR"
    
    generated_ids = outputs[0][input_len:]
    decoded = tokenizer.decode(generated_ids, skip_special_tokens=False)
    print(f"\n---- Model Answer ----\n{decoded.strip()}\n--------------")
    return decoded.strip()

def generate_multimodal_answer(model, processor, messages, max_new_tokens=1024):
    """
    Generates an answer using a vision-language model.
    This function does not expect an image.
    It uses the processor's chat template logic.
    """
    try:
        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt"
        ).to(model.device, dtype=torch.bfloat16)
    except Exception as e:
        print(f"Error during processor template application: {e}")
        return "ERROR"

    input_len = inputs["input_ids"].shape[-1]
    with torch.inference_mode():
        generation = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        generation = generation[0][input_len:]
    decoded = processor.decode(generation, skip_special_tokens=False)
    return decoded.strip()

def generate_answer(model, proc_or_tok, messages, modality="Text", use_chat_template=True, max_length=2048):
    """
    Wrapper that calls the appropriate generation function based on modality.
    
    - For modality "Text", it calls generate_text_answer.
    - For modality "Text+Vision", it calls generate_multimodal_answer.
    """
    if modality == "Text":
        return generate_text_answer(model, proc_or_tok, messages, use_chat_template, max_length)
    else:
        return generate_multimodal_answer(model, proc_or_tok, messages, max_new_tokens=max_length)

# ---------------- Main Processing Function ----------------

def main():
    parser = argparse.ArgumentParser(description='Generate model answers for a dataset (supports Text and Text+Vision modalities).')
    parser.add_argument('--model_path', type=str, required=True, help='Path or model_id to the model directory.')
    parser.add_argument('--license', type=str, required=True, help='License for the model.')
    parser.add_argument('--revision', type=str, required=True, help='Model revision.')
    parser.add_argument('--precision', type=str, default='fp32', help='Precision to load the model (e.g., fp32, fp16, bf16).')
    parser.add_argument('--params', type=str, default=None, help='Optional: Number of parameters as a numerical string.')
    parser.add_argument('--modality', type=str, default='Text', choices=["Text", "Text+Vision"], help='Modality: "Text" for text-only models, "Text+Vision" for vision-language models.')
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input JSON file.')
    parser.add_argument('--output', type=str, required=True, help='Directory to save the output JSON file.')
    parser.add_argument('--batch', type=str, default='1', help='Batch number.')
    parser.add_argument('--force_multi_gpu', action='store_true', help='Force loading the model across multiple GPUs.')
    args = parser.parse_args()

    # Set GPU memory assumption (GiB per GPU)
    GPU_MEMORY = 75 if args.modality == "Text" else 79

    # Extract model name details.
    org, model_id, raw_model_name = extract_model_name(args.model_path)
    print(f"Provider: {org}")
    print(f"Model ID: {model_id}")
    print(f"Raw Model Name: {raw_model_name}")

    if not torch.cuda.is_available():
        print("Error: No GPUs available. Please ensure GPUs are accessible.")
        exit(1)
    else:
        print(f"Number of GPUs available: {torch.cuda.device_count()}")

    # Load the dataset.
    try:
        with open(args.input_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except Exception as e:
        print(f"Error loading input file: {e}")
        exit(1)
    total_entries = len(data)
    print(f"Total number of entries: {total_entries}")

    script_start_time = time.time()
    print(f"\nProcessing model: {raw_model_name}")
    model_start_time = time.time()

    # Estimate model size and parameters.
    total_size_bytes = get_model_folder_size(args.model_path)
    print(f"Model size in bytes: {total_size_bytes}")
    bits_per_param = get_precision_bits(args.precision)
    print(f"Bits per parameter: {bits_per_param}")

    if args.params and args.params.isdigit():
        total_params_in_billion = float(args.params)
        print(f"Using provided --params value: {total_params_in_billion} billion parameters.")
    else:
        total_params = estimate_model_parameters_by_size(total_size_bytes, bits_per_param)
        total_params_in_billion = total_params / 1e9
        print(f"Estimated total parameters: {round(total_params_in_billion, 3)} billion")

    # Set threshold (different for Text and Text+Vision models).
    if args.modality == "Text":
        threshold = 20_000_000_000  # 20 billion parameters
    else:
        threshold = 10_000_000_000   # 10 billion parameters

    precision_map = {
        'fp32': torch.float32,
        'float32': torch.float32,
        'fp16': torch.float16,
        'float16': torch.float16,
        'bf16': torch.bfloat16,
        'bfloat16': torch.bfloat16,
        'int8': torch.int8
    }
    torch_dtype = precision_map.get(args.precision.lower(), torch.float32)

    # ---------------- Model & Processor/Tokenizer Loading ----------------

    if args.modality == "Text":
        print(f"Loading tokenizer for text model {raw_model_name}")
        try:
            tokenizer = AutoTokenizer.from_pretrained(args.model_path, trust_remote_code=True)
            tok_or_pro = tokenizer
        except Exception as e:
            print(f"Error loading tokenizer: {e}")
            exit(1)
        # Decide multi-GPU loading for text models.
        if args.force_multi_gpu or (total_params_in_billion * 1e9 > threshold):
            print("Loading text model with device_map='auto' across multiple GPUs.")
            torch.cuda.empty_cache()
            gc.collect()
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    args.model_path,
                    device_map="auto",
                    trust_remote_code=True
                )
            except Exception as e:
                print(f"Error loading text model with device_map='auto': {e}")
                exit(1)
        else:
            print("Loading text model on single GPU.")
            torch.cuda.empty_cache()
            gc.collect()
            free_gpu_id = get_free_gpu_id()
            print(f"Using GPU {free_gpu_id} for text model.")
            try:
                model = AutoModelForCausalLM.from_pretrained(
                    args.model_path,
                    device_map={"": free_gpu_id},
                    torch_dtype=torch_dtype,
                    trust_remote_code=True
                )
            except Exception as e:
                print(f"Error loading text model on single GPU: {e}")
                exit(1)
        # Detect if chat template exists.
        use_chat_template = hasattr(tokenizer, 'chat_template') and getattr(tokenizer, 'chat_template', None)
        if use_chat_template:
            print("Chat template detected, using it for formatting.")
        else:
            print("No chat template detected; proceeding with standard tokenization.")
    else:  # modality == "Text+Vision"
        print(f"Loading processor for vision model {raw_model_name}")
        try:
            processor = AutoProcessor.from_pretrained(args.model_path, trust_remote_code=True)
            tok_or_pro = processor
        except Exception as e:
            print(f"Error loading processor: {e}")
            exit(1)
        # Decide multi-GPU loading for vision models.
        if args.force_multi_gpu or (total_params_in_billion * 1e9 > threshold):
            print("Loading vision model with device_map='auto' across multiple GPUs (with offloading).")
            torch.cuda.empty_cache()
            gc.collect()
            n_gpus = torch.cuda.device_count()
            max_memory = {i: f"{GPU_MEMORY}GiB" for i in range(n_gpus)}
            try:
                model = AutoModelForVision2Seq.from_pretrained(
                    args.model_path,
                    device_map="auto",
                    max_memory=max_memory,
                    offload_folder="offload",
                    offload_state_dict=True,
                    low_cpu_mem_usage=True,
                    torch_dtype=torch_dtype,
                    trust_remote_code=True
                )
            except Exception as e:
                print(f"Error loading vision model with device_map='auto': {e}")
                exit(1)
        else:
            print("Loading vision model on single GPU.")
            torch.cuda.empty_cache()
            gc.collect()
            free_gpu_id = get_free_gpu_id()
            print(f"Using GPU {free_gpu_id} for vision model.")
            try:
                model = AutoModelForVision2Seq.from_pretrained(
                    args.model_path,
                    torch_dtype=torch_dtype,
                    device_map={"": free_gpu_id},
                    trust_remote_code=True
                )
            except Exception as e:
                print(f"Error loading vision model on single GPU: {e}")
                exit(1)
        # Check for chat template availability and assign to use_chat_template.
        try:
            if args.model_path.startswith("/"):
                model_dir = args.model_path
            else:
                model_dir = snapshot_download(repo_id=args.model_path, local_files_only=False)
            chat_template_path = Path(model_dir) / "chat_template.json"
            if chat_template_path.is_file():
                use_chat_template = True
                print("Chat template detected, using it for prompt formatting.")
            else:
                use_chat_template = False
                print("No chat template found; proceeding without it.")
        except Exception as e:
            print(f"Error checking for chat template: {e}")
            use_chat_template = False

    # ---------------- Process Dataset & Generate Answers ----------------

    results = []
    generation_count = 0

    for entry in data:
        updated_entry = copy.deepcopy(entry)
        meta = updated_entry.get("Meta", {})
        test = updated_entry.get("Test", {})
        model_section = {}

        # Update metadata with model info.
        meta['Model Name'] = raw_model_name
        meta['License'] = args.license
        meta['Revision'] = args.revision
        meta['Precision'] = args.precision
        meta['Params'] = round(total_params_in_billion, 3)

        # Define the system prompt based on language
        language = meta.get("Language", "").lower()
        
        if language == "arabic":
            system_prompt = "أنت مساعد ذو معرفة قادر على الإجابة على أسئلة مختلفة، وخاصة تلك المتعلقة بالتاريخ والثقافة والمعرفة العامة."
        elif language == "hindi":
            system_prompt = "आप एक जानकार सहायक हैं जो विभिन्न प्रश्नों का उत्तर देने में सक्षम हैं, विशेष रूप से इतिहास, संस्कृति और सामान्य ज्ञान से संबंधित प्रश्नों का।"
        else:
            system_prompt = "You are a knowledgeable assistant capable of answering various questions, especially those related to history, culture, and general knowledge. Please answer in the same language as the question is asked."

        round_number = meta.get("Round", 0)
        if round_number == 0:
            question1 = test.get("Question 1", "").strip()
            if not question1:
                print(f"Warning: Empty 'Question 1' in entry SN {meta.get('SN.')}. Skipping entry.")
                continue
            # For Text+Vision, include a system message in the expected format.
            if args.modality == "Text+Vision":
                messages = [
                    {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "text", "text": question1}]}
                ]
            else:
                messages = []
                if not use_chat_template:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": question1})
            answer = generate_answer(model, tok_or_pro, messages, modality=args.modality, use_chat_template=use_chat_template)
            model_section['Answer 1'] = answer if answer else "None"
        elif round_number == 1:
            question1 = test.get("Question 1", "").strip()
            question2 = test.get("Question 2", "").strip()
            if not question1 or not question2:
                print(f"Warning: Missing questions in entry SN {meta.get('SN.')}. Skipping entry.")
                continue
            answer1 = test.get("Answer 1", "").strip()
            if not answer1:
                if args.modality == "Text+Vision":
                    messages_a1 = [
                        {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                        {"role": "user", "content": [{"type": "text", "text": question1}]}
                    ]
                else:
                    messages_a1 = []
                    if not use_chat_template:
                        messages_a1.append({"role": "system", "content": system_prompt})
                    messages_a1.append({"role": "user", "content": question1})
                answer1 = generate_answer(model, tok_or_pro, messages_a1, modality=args.modality, use_chat_template=use_chat_template)
                model_section['Answer 1'] = answer1 if answer1 else "None"
            if args.modality == "Text+Vision":
                messages = [
                    {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "text", "text": question1}]},
                    {"role": "assistant", "content": [{"type": "text", "text": answer1}]},
                    {"role": "user", "content": [{"type": "text", "text": question2}]}
                ]
            else:
                messages = []
                if not use_chat_template:
                    messages.append({"role": "system", "content": system_prompt})
                messages.extend([
                    {"role": "user", "content": question1},
                    {"role": "assistant", "content": answer1},
                    {"role": "user", "content": question2}
                ])
            refined_answer = generate_answer(model, tok_or_pro, messages, modality=args.modality, use_chat_template=use_chat_template)
            model_section['Answer 1'] = refined_answer if refined_answer else "None"
        elif round_number == 2:
            question1 = test.get("Question 1", "").strip()
            question2 = test.get("Question 2", "").strip()
            if not question1 or not question2:
                print(f"Warning: Missing questions in entry SN {meta.get('SN.')}. Skipping entry.")
                continue
            if args.modality == "Text+Vision":
                messages_a1 = [
                    {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "text", "text": question1}]}
                ]
            else:
                messages_a1 = []
                if not use_chat_template:
                    messages_a1.append({"role": "system", "content": system_prompt})
                messages_a1.append({"role": "user", "content": question1})
            answer1 = generate_answer(model, tok_or_pro, messages_a1, modality=args.modality, use_chat_template=use_chat_template)
            model_section['Answer 1'] = answer1 if answer1 else "None"
            if args.modality == "Text+Vision":
                messages = [
                    {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "text", "text": question1}]},
                    {"role": "assistant", "content": [{"type": "text", "text": answer1}]},
                    {"role": "user", "content": [{"type": "text", "text": question2}]}
                ]
            else:
                messages = []
                if not use_chat_template:
                    messages.append({"role": "system", "content": system_prompt})
                messages.extend([
                    {"role": "user", "content": question1},
                    {"role": "assistant", "content": answer1},
                    {"role": "user", "content": question2}
                ])
            answer2 = generate_answer(model, tok_or_pro, messages, modality=args.modality, use_chat_template=use_chat_template)
            model_section['Answer 2'] = answer2 if answer2 else "None"
        else:
            print(f"Warning: Unsupported round {meta.get('Round')} in entry SN {meta.get('SN.')}. Skipping entry.")
            continue

        updated_entry['Meta'] = meta
        updated_entry['Model'] = model_section
        generation_count += 1
        print(f"Processed {generation_count}/{total_entries} entries for model {raw_model_name}")
        results.append(updated_entry)

    model_end_time = time.time()
    model_elapsed = model_end_time - model_start_time
    hrs, rem = divmod(model_elapsed, 3600)
    mins, secs = divmod(rem, 60)
    print(f"Total time for {raw_model_name}: {int(hrs):02}:{int(mins):02}:{secs:05.2f}")

    output_file_name = f"{org}_{model_id}_{args.revision}_{args.precision}_answers.json"
    output_file_path = os.path.join(args.output, output_file_name)
    os.makedirs(args.output, exist_ok=True)

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"Results saved to {output_file_path}")
    except Exception as e:
        print(f"Error saving results for {raw_model_name}: {e}")

    # Cleanup.
    del model
    if args.modality == "Text":
        del tokenizer
    else:
        del processor
    torch.cuda.empty_cache()
    gc.collect()

    total_elapsed = time.time() - script_start_time
    hrs, rem = divmod(total_elapsed, 3600)
    mins, secs = divmod(rem, 60)
    print(f"\nTotal script time: {int(hrs):02}:{int(mins):02}:{secs:05.2f}")

if __name__ == "__main__":
    main()
