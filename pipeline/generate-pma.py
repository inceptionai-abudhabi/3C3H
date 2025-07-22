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
This script generates answers to the passed dataset for Proprietary Models using the providers' APIs.
"""

import os
import time
import json
import argparse
import re

# For OpenAI and Inception models
from openai import OpenAI, AzureOpenAI

# For Anthropic API
from anthropic import Anthropic

# ==========================
# Configuration Parameters
# ==========================

# Read API keys from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
inception_api_key = os.getenv("INCEPTION_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")
deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
mistral_api_key = os.getenv("MISTRAL_API_KEY")
xai_api_key = os.getenv("XAI_API_KEY")

# Check for missing keys
missing_keys = []
if not openai_api_key:
    missing_keys.append("OPENAI_API_KEY")
if not anthropic_api_key:
    missing_keys.append("ANTHROPIC_API_KEY")
if not inception_api_key:
    missing_keys.append("INCEPTION_API_KEY")
if not google_api_key:
    missing_keys.append("GOOGLE_API_KEY")
if not deepseek_api_key:
    missing_keys.append("DEEPSEEK_API_KEY")
if not mistral_api_key:
    missing_keys.append("MISTRAL_API_KEY")
if not xai_api_key:
    missing_keys.append("XAI_API_KEY")

if missing_keys:
    print(f"Error: The following environment variables are not set: {', '.join(missing_keys)}")


def openai_generate_answer(model_name, messages, api_key, max_tokens=2048):
    """
    Generates an assistant reply using the OpenAI API.
    """
    # Initialize the OpenAI client
    client = OpenAI(api_key=api_key)
    try:
        if re.match(r'^o\d', model_name):
            messages = [msg for msg in messages if msg.get("role") != "system"]
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            assistant_reply = response.choices[0].message.content.strip()
        else:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.0,        # Try to control the generation consistency
                max_tokens=max_tokens
            )
            assistant_reply = response.choices[0].message.content.strip()
        
        return assistant_reply
    except Exception as e:
        error_message = f"Error during OpenAI API call ({model_name}): {str(e)}"
        print(error_message)
        return "ERROR"

def anthropic_generate_answer(model_name, messages, api_key, max_tokens=2048):
    """
    Generates an assistant reply using the Anthropic API.
    """
    # Initialize the Anthropic client
    client = Anthropic(api_key=api_key)

    try:
        # Separate the system prompt and user messages
        system_prompt = ''
        if messages and messages[0]['role'] == 'system':
            system_prompt = messages[0]['content']
            messages = messages[1:]  # Remove the system message from messages
        
        # Convert messages to the format expected by Anthropic
        conversation = []
        for msg in messages:
            if msg['role'] == 'user':
                conversation.append({"role": "user", "content": [{"type": "text", "text": msg['content']}]})
            elif msg['role'] == 'assistant':
                conversation.append({"role": "assistant", "content": [{"type": "text", "text": msg['content']}]})
            else:
                continue  # Skip any other message types

        response = client.messages.create(
            model=model_name,
            system=system_prompt,
            messages=conversation,
            temperature=0.0,        # Try to control the generation consistency
            max_tokens=max_tokens
        )
        assistant_reply = response.content[0].text
        time.sleep(1)  # Sleep to respect API rate limits
        return assistant_reply
    except Exception as e:
        error_message = f"Error during Anthropic API call ({model_name}): {str(e)}"
        print(error_message)
        return "ERROR"

def inception_generate_answer(model_name, messages, api_key, max_tokens=2048):
    """
    Generates an assistant reply using the Inception AI API.
    """
    # Set up the base URLs and model names based on the model_name
    if model_name == 'jais-30b':
        openai_api_base = "https://jais-v2-web-inference-dev.inceptionai.ai/v1"
    elif model_name == 'jais-70b':
        openai_api_base = "https://jais-v2-web-inference-70b-dev.inceptionai.ai/v1"
    elif model_name == 'k2-65b':
        openai_api_base = "https://jais-v2-web-inference-65b-dev.inceptionai.ai/v1"
        model_name = 'jais-65b'
    elif model_name == 'llama3.1-405b':
        openai_api_base = "http://176.56.198.97:8076/v1"
        model_name = "/project/LLAMA_FAMILY/llama-models/models/llama3_1/HF_MODELS/Meta-Llama-3.1-405B-Instruct-FP8"
    else:
        print(f"Unknown Inception model name: {model_name}")
        return "ERROR"

    # Initialize the OpenAI client
    client = OpenAI(
        api_key=api_key,
        base_url=openai_api_base
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,        # Try to control the generation consistency
            max_tokens=max_tokens
        )
        assistant_reply = response.choices[0].message.content.strip()
        return assistant_reply
    except Exception as e:
        error_message = f"Error during Inception API call ({model_name}): {str(e)}"
        print(error_message)
        return "ERROR"

def google_generate_answer(model_name: str,
                           messages: list[dict],
                           api_key: str,
                           max_tokens: int = 2048) -> str:
    """
    Generates an assistant reply using **Google Gemini models through the OpenAI-compatible endpoint.
    """

    # Gemini's OpenAI-compatible base URL
    GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Initialise the OpenAI client *pointing to Gemini*
    client = OpenAI(
        api_key=api_key,
        base_url=GEMINI_BASE,
    )

    try:
        # Gemini works fine with a system message, so send the conversation as-is
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,        # deterministic output
            max_tokens=max_tokens,
            n=1,
        )
        assistant_reply = response.choices[0].message.content.strip()
        # Be a bit gentle on the rate-limit
        # time.sleep(0.5)
        return assistant_reply
    except Exception as exc:
        print(f"Error during Google Gemini (OpenAI client) call ({model_name}): {exc}")
        return "ERROR"

# def google_generate_answer(model_name, messages, api_key):
#     """
#     Generates an assistant reply using the Google Gemini API.
#     """
#     # Configure the Google Gemini API key
#     genai.configure(api_key=api_key)

#     try:
#         # Initialize the model with system instruction
#         system_prompt = ''
#         if messages and messages[0]['role'] == 'system':
#             system_prompt = messages[0]['content']

#         model = genai.GenerativeModel(
#             model_name=model_name,
#             system_instruction=system_prompt
#         )

#         # Start a chat with any previous history
#         history = []
#         for message in messages[1:]:  # Skip the system prompt
#             role = 'user' if message['role'] == 'user' else 'model'
#             history.append({"role": role, "parts": message['content']})

#         chat = model.start_chat(history=history)

#         # Send the latest user message
#         last_user_message = messages[-1]['content'] if messages[-1]['role'] == 'user' else ''
#         response = chat.send_message(
#             last_user_message
#         )
#         assistant_reply = response.text.strip()
#         # Optional: Sleep to respect API rate limits
#         time.sleep(0.5)
#         return assistant_reply
#     except Exception as e:
#         error_message = f"Error during Google Gemini API call ({model_name}): {str(e)}"
#         print(error_message)
#         return "ERROR"

def deepseek_generate_answer(model_name, messages, api_key, max_tokens=2048):
    """
    Generates an assistant reply using the DeepSeek API.
    """
    # Initialize the OpenAI client
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,        # Try to control the generation consistency
            max_tokens=max_tokens
        )
        assistant_reply = response.choices[0].message.content.strip()
        return assistant_reply
    except Exception as e:
        error_message = f"Error during DeepSeek API call ({model_name}): {str(e)}"
        print(error_message)
        return "ERROR"

def mistral_generate_answer(model_name, messages, api_key, max_tokens=2048):
    """
    Generates an assistant reply using the Mistral API.
    """
    try:
        from mistralai import Mistral
    except ImportError:
        print("Error: The 'mistralai' module is not installed.")
        return "ERROR"
    
    client = Mistral(api_key=api_key)
    try:
        chat_response = client.chat.complete(
            model=model_name,
            messages=messages
        )
        assistant_reply = chat_response.choices[0].message.content.strip()
        return assistant_reply
    except Exception as e:
        error_message = f"Error during Mistral API call ({model_name}): {str(e)}"
        print(error_message)
        return "ERROR"

def xai_generate_answer(model_name, messages, api_key, max_tokens=2048):
    """
    Generates an assistant reply using the OpenAI API.
    Retries once with a 60-second wait if a 429 "Too many requests" error occurs.
    If the error persists after the retry, returns "ERROR".
    """
    # Initialize the OpenAI client
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    
    for attempt in range(2):
        try:
            if "o1" in model_name or "o3" in model_name:
                # Remove system messages for specific models
                filtered_messages = [msg for msg in messages if msg.get("role") != "system"]
                response = client.chat.completions.create(
                    model=model_name,
                    messages=filtered_messages
                )
            else:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.0,  # Control generation consistency
                    max_tokens=max_tokens
                )
            assistant_reply = response.choices[0].message.content.strip()
            return assistant_reply
        
        except Exception as e:
            error_str = str(e)
            print(f"Error during xAI API call ({model_name}): {error_str}")
            if attempt == 0 and "429" in error_str and "Too many requests" in error_str:
                print("Received 429 error: Too many requests. Waiting 60 seconds before retrying...")
                time.sleep(60)
            else:
                return "ERROR"

def generate_model_answer(provider, model_name, messages, max_tokens=2048):
    """
    Generates an assistant reply using the specified provider and model_name.
    """
    if provider == 'openai':
        answer = openai_generate_answer(model_name, messages, openai_api_key, max_tokens)
    elif provider == 'anthropic':
        answer = anthropic_generate_answer(model_name, messages, anthropic_api_key, max_tokens)
    elif provider == 'inception':
        answer = inception_generate_answer(model_name, messages, inception_api_key, max_tokens)
    elif provider == 'google':
        answer = google_generate_answer(model_name, messages, google_api_key)
    elif provider == 'deepseek':
        answer = deepseek_generate_answer(model_name, messages, deepseek_api_key)
    elif provider == 'mistral':
        answer = mistral_generate_answer(model_name, messages, mistral_api_key, max_tokens)
    elif provider == 'xai':
        answer = xai_generate_answer(model_name, messages, xai_api_key, max_tokens)
    else:
        print(f"Unknown provider: {provider}")
        answer = "ERROR"
    print(f"\n---- Model Answer ----\n{answer.strip()}\n--------------")
    return answer.strip()

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Generate model answers for the dataset using Proprietary Models.')
    parser.add_argument('--model_name', type=str, required=True, help='Name of the proprietary model (e.g., gpt-4, mistral-saba-2502).')
    parser.add_argument('--input_file', type=str, required=True, help='Path to the input JSON file.')
    parser.add_argument('--output', type=str, required=True, help='Directory to save the output JSON file.')
    parser.add_argument('--batch', type=str, default='1', help='Batch number.')
    args = parser.parse_args()

    # Extract model_name
    raw_model_name = args.model_name

    # Load the dataset from the JSON file
    try:
        with open(args.input_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"Error: The file {args.input_file} was not found.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file {args.input_file}: {e}")
        exit(1)

    total_entries = len(data)
    print(f"Total number of entries in the file: {total_entries}")

    # Record the start time of the script
    script_start_time = time.time()

    print(f"\nProcessing model: {raw_model_name}")
    model_start_time = time.time()

    # Initialize counter
    generation_count = 0

    # Prepare results list for this model
    results = []

    # Determine which provider to use based on model_name
    model_name_lower = raw_model_name.lower()
    if 'gpt' in model_name_lower or 'o1' in model_name_lower or 'o3' in model_name_lower or 'o4' in model_name_lower:
        provider = 'openai'
    elif 'claude' in model_name_lower:
        provider = 'anthropic'
    elif 'jais' in model_name_lower or 'k2' in model_name_lower or 'llama' in model_name_lower:
        provider = 'inception'
    elif 'gemini' in model_name_lower:
        provider = 'google'
    elif 'deepseek' in model_name_lower:
        provider = 'deepseek'
    elif 'mistral' in model_name_lower:
        provider = 'mistral'
    elif 'grok' in model_name_lower:
        provider = 'xai'
    else:
        print(f"Unknown proprietary model: {raw_model_name}")
        exit(1)

    # Process each entry in the dataset
    for entry in data:
        # Copy the entry to avoid modifying the original data
        updated_entry = entry.copy()
        meta = updated_entry.get("Meta", {})
        test = updated_entry.get("Test", {})
        model_section = updated_entry.get("Model", {})
        round_number = meta.get("Round", 0)  # Default to 0 if not specified

        # Update Meta section with model information
        meta['Model Name'] = raw_model_name
        meta['License'] = "Proprietary"
        meta['Revision'] = "UNK"  # Revisions are unknown for proprietary models
        meta['Precision'] = "UNK"  # Precisions are unknown for proprietary models
        meta['Params'] = "UNK"  # Parameters are unknown for proprietary models
    
        # Define the system prompt based on language
        language = meta.get("Language", "").lower()
        
        if language == "arabic":
            system_prompt = "أنت مساعد ذو معرفة قادر على الإجابة على أسئلة مختلفة، وخاصة تلك المتعلقة بالتاريخ والثقافة والمعرفة العامة."
        elif language == "hindi":
            system_prompt = "आप एक जानकार सहायक हैं जो विभिन्न प्रश्नों का उत्तर देने में सक्षम हैं, विशेष रूप से इतिहास, संस्कृति और सामान्य ज्ञान से संबंधित प्रश्नों का।"
        else:
            system_prompt = "You are a knowledgeable assistant capable of answering various questions, especially those related to history, culture, and general knowledge. Please answer in the same language as the question is asked."
    
        # Handle different rounds/categories
        if round_number == 0:
            # Default Categories
            question1 = test.get("Question 1", "").strip()
            if not question1:
                print(f"Warning: Empty 'Question 1' in entry with SN {meta.get('SN.')}")
                continue

            # Prepare the prompt for 'Answer 1'
            messages = []
            messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": question1})

            # Generate 'Answer 1'
            assistant_reply = generate_model_answer(provider, raw_model_name, messages)
            model_section['Answer 1'] = assistant_reply if assistant_reply else "ERROR"

        elif round_number == 1:
            # "Conversational Questions" Category
            question1 = test.get("Question 1", "").strip()
            question2 = test.get("Question 2", "").strip()

            if not question1 or not question2:
                print(f"Warning: Empty 'Question 1' or 'Question 2' in entry with SN {meta.get('SN.')}")
                continue

            # Retrieve 'Answer 1' if it exists; else generate it
            answer1 = test.get('Answer 1', "").strip()
            if not answer1:
                print(f"Warning: Empty 'Answer 1' in entry with SN {meta.get('SN.')} from Round==1. GENERATING IT.")
                # Generate 'Answer 1' from 'Question 1'
                messages_a1 = []
                messages_a1.append({"role": "system", "content": system_prompt})
                messages_a1.append({"role": "user", "content": question1})
                answer1 = generate_model_answer(provider, raw_model_name, messages_a1)
                model_section['Answer 1'] = answer1 if answer1 else "ERROR"

            # Now, use 'Question 1', 'Answer 1', and 'Question 2' to generate the final 'Answer 1'
            messages = []
            messages.append({"role": "system", "content": system_prompt})
            messages.extend([
                {"role": "user", "content": question1},
                {"role": "assistant", "content": answer1},
                {"role": "user", "content": question2}
            ])

            # Generate updated 'Answer 1'
            assistant_reply = generate_model_answer(provider, raw_model_name, messages)
            model_section['Answer 1'] = assistant_reply if assistant_reply else "ERROR"

        elif round_number == 2:
            # "Follow-up Questions" Category
            question1 = test.get("Question 1", "").strip()
            question2 = test.get("Question 2", "").strip()

            if not question1 or not question2:
                print(f"Warning: Empty 'Question 1' or 'Question 2' in entry with SN {meta.get('SN.')}")
                continue

            # Generate 'Answer 1' from 'Question 1'
            messages_a1 = []
            messages_a1.append({"role": "system", "content": system_prompt})
            messages_a1.append({"role": "user", "content": question1})
            assistant_reply1 = generate_model_answer(provider, raw_model_name, messages_a1)
            model_section['Answer 1'] = assistant_reply1 if assistant_reply1 else "ERROR"

            # Now, use 'Question 1', 'Answer 1', and 'Question 2' to generate 'Answer 2'
            messages = []
            messages.append({"role": "system", "content": system_prompt})
            messages.extend([
                {"role": "user", "content": question1},
                {"role": "assistant", "content": assistant_reply1},
                {"role": "user", "content": question2}
            ])

            # Generate 'Answer 2'
            assistant_reply2 = generate_model_answer(provider, raw_model_name, messages)
            model_section['Answer 2'] = assistant_reply2 if assistant_reply2 else "ERROR"

        else:
            print(f"Warning: Unsupported 'Round' value {round_number} or mismatched category in entry with SN {meta.get('SN.')}")
            continue

        # Update the 'Meta' and 'Model' sections in the entry
        updated_entry['Meta'] = meta
        updated_entry['Model'] = model_section

        generation_count += 1
        print(f"Generation: {generation_count}/{total_entries} for model {raw_model_name}")

        results.append(updated_entry)

    # Record the end time for this model
    model_end_time = time.time()
    # Calculate the elapsed time
    model_elapsed_time = model_end_time - model_start_time
    # Format the elapsed time into hours, minutes, and seconds
    hours, rem = divmod(model_elapsed_time, 3600)
    minutes, seconds = divmod(rem, 60)
    print(f"Total time taken for {raw_model_name}: {int(hours):0>2}:{int(minutes):0>2}:{seconds:05.2f}")

    # Output file path for this model
    safe_model_name = raw_model_name.replace('/', '_').replace(' ', '_')
    output_file_name = f"{provider}_{safe_model_name}_{meta['Revision']}_{meta['Precision']}_answers.json"
    output_file_path = os.path.join(args.output, output_file_name)

    # Ensure the output directory exists
    os.makedirs(args.output, exist_ok=True)

    # Write the updated data back to the JSON file specific to the model
    try:
        with open(output_file_path, 'w', encoding='utf-8') as file:
            json.dump(results, file, ensure_ascii=False, indent=4)
        print(f"Results saved to {output_file_path}\n")
    except Exception as e:
        print(f"Error saving results for {raw_model_name}: {e}")

    # Record the end time of the script
    script_end_time = time.time()
    # Calculate the total elapsed time
    total_elapsed_time = script_end_time - script_start_time
    # Format the elapsed time into hours, minutes, and seconds
    hours, rem = divmod(total_elapsed_time, 3600)
    minutes, seconds = divmod(rem, 60)
    print(f"\nTotal time taken: {int(hours):0>2}:{int(minutes):0>2}:{seconds:05.2f}")

if __name__ == "__main__":
    main()
