import argparse
import sys
import threading
import time
import itertools
import subprocess
import os
import json
from langchain_ollama import OllamaLLM  # Updated import
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Initialize the Ollama model
llm = OllamaLLM(model="LlamaCLI")  # Updated model initialization

# Chat history to maintain conversation state
chat_history = []

# Define the prompt template
prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a linux terminal assistant, the user will ask you how to perform specific tasks using bash script and your job is to only give him the commands he has to use without any unnecessary comments.",
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ]
)

# Chain of prompt template and LLM
chain = prompt_template | llm

# File to store memory for chat history persistence
MEMORY_FILE = 'ollama_chat_history.json'

def loading_spinner():
    spinner = itertools.cycle(['-', '/', '|', '\\'])
    while not stop_spinner_event.is_set():
        sys.stdout.write(next(spinner))
        sys.stdout.flush()
        time.sleep(0.1)
        sys.stdout.write('\b')

def load_chat_history():
    """Load chat history from a file."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            history_data = json.load(f)
            # Convert the JSON to HumanMessage and AIMessage objects
            for entry in history_data:
                if entry["role"] == "human":
                    chat_history.append(HumanMessage(content=entry["content"]))
                elif entry["role"] == "ai":
                    chat_history.append(AIMessage(content=entry["content"]))

def save_chat_history():
    """Save chat history to a file."""
    with open(MEMORY_FILE, 'w') as f:
        history_data = []
        for message in chat_history:
            role = "human" if isinstance(message, HumanMessage) else "ai"
            history_data.append({"role": role, "content": message.content})
        json.dump(history_data, f, indent=4)

def run_ollama(command, execute_flag=False, filename=None):
    global stop_spinner_event
    stop_spinner_event = threading.Event()

    # Load chat history from the file
    load_chat_history()

    spinner_thread = threading.Thread(target=loading_spinner)
    spinner_thread.start()

    if filename:
        full_command = f"File: {filename}\nCommand: {command.strip()}"
    else:
        full_command = f"Command: {command.strip()}"

    # Append the user command to the chat history
    chat_history.append(HumanMessage(content=full_command))

    # Invoke the model using the chat history
    response = chain.invoke({"input": command, "chat_history": chat_history})

    stop_spinner_event.set()
    spinner_thread.join()

    # Append the model's response to the chat history
    chat_history.append(AIMessage(content=response))

    # Save the updated chat history
    save_chat_history()

    print(response)

    # Check for potentially dangerous commands (e.g., rm)
    dangerous_commands = ['rm', 'rmdir', 'sudo rm']
    contains_dangerous = any(cmd in response for cmd in dangerous_commands)

    if execute_flag:
        if contains_dangerous:
            confirmation = input(f"The command contains a potentially dangerous operation ('rm'). Are you sure you want to execute it? (y/n): ").strip().lower()
            if confirmation != 'y':
                print("Command execution aborted.")
                return

        subprocess.run(response, shell=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run commands with Ollama and optionally execute output.")
    parser.add_argument("command", help="Command to pass to the model.")
    parser.add_argument("-e", "--execute", action="store_true", help="Automatically execute the command given by the model.")
    parser.add_argument("-f", "--file", help="Specify the input filename.")

    args = parser.parse_args()

    run_ollama(args.command, args.execute, filename=args.file)