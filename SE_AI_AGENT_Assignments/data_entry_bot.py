import pyautogui
import time
import os
import random

# --- Configuration ---
# FIX: Use a raw string (r"...") for the Windows path to avoid escape sequence errors.
DATA_FILE = r"C:\Users\Hi\Desktop\python_tutorial\sendan\pyautogui Assign\data_input.txt"
# Time in seconds to pause between operations for stability and observation
PAUSE_TIME = 0.2 
# Time in seconds to wait for the target application to fully open
SETUP_DELAY = 3 

def run_data_entry_bot():
    print("--- PyAutoGUI Data Entry Bot Starting ---")
    
    # 1. Read Data from File
    try:
        # The file reading logic is correct
        with open(DATA_FILE, 'r') as f:
            data_lines = f.readlines()
        
        if not data_lines:
            print(f"Error: {DATA_FILE} is empty.")
            return

    except FileNotFoundError:
        print(f"Error: Data file '{DATA_FILE}' not found.")
        return

    # 2. Automatically Open and Focus the Target Application
    print("\nAttempting to open Notepad...")
    try:
        # Opens Notepad on Windows. This usually brings it into focus.
        os.startfile("notepad.exe") 
    except Exception as e:
        print(f"Could not open Notepad automatically: {e}")
        print("Please open Notepad manually and click inside it immediately.")
        
    print(f"Waiting {SETUP_DELAY} seconds for Notepad to load and gain focus...")
    time.sleep(SETUP_DELAY)

    # 3. Setup PyAutoGUI
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = PAUSE_TIME 

    # 4. Automation Core Logic
    
    print("\n--- Starting Data Entry ---")
    for i, line in enumerate(data_lines):
        # Clean up the line (remove extra spaces and newline characters)
        line = line.strip()
        if not line:
            continue

        try:
            name, age = [item.strip() for item in line.split(',')]
        except ValueError:
            print(f"Skipping line {i+1}: Invalid format. Expected 'Name, Age'.")
            continue

        print(f"Entering data for: {name}, {age}")

        # --- A. Enter Name and Age (with a comma and space for readability) ---
        # Instead of pressing TAB, just type the full entry and a newline.
        # This is more suitable for a simple text editor like Notepad.
        full_entry = f"{name}, {age}" 
        
        pyautogui.write(full_entry)
        
        # Press ENTER to move to the next line
        pyautogui.press('enter') 

        # Optional: Add a small, random human-like delay between records
        time.sleep(random.uniform(0.1, 0.5))

    print("\n--- Data Entry Complete! ---")
    print(f"Successfully processed {len(data_lines)} records.")

if __name__ == "__main__":
    run_data_entry_bot()