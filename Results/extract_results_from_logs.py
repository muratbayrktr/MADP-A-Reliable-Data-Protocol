import re


def extract_information(text):
    # Split the text into lines
    lines = text.split('\n')

    # Pattern to match the lines with "Run[", "normaldelay", and "Total Time:"
    run_pattern = re.compile(r'Run\[(\d+)\]\[(\w+)\]\[(\d+)%\]:')
    time_pattern = re.compile(r'Total Time:\s+(\d+\.\d+)')

    # List to hold the extracted information
    extracted_info = []

    # Variables to hold current run number, normaldelay, and percentage
    current_run = None
    current_normaldelay = None
    current_percentage = None

    for line in lines:
        # Check if the line contains "Run["
        run_match = run_pattern.search(line)
        if run_match:
            current_run = run_match.group(1)
            current_normaldelay = run_match.group(2)
            current_percentage = run_match.group(3)
            continue
        
        # Check if the line contains "Total Time:"
        time_match = time_pattern.search(line)
        if time_match and current_run is not None:
            total_time = time_match.group(1)
            extracted_info.append(f'madp,{current_normaldelay},{current_percentage},{current_run},{total_time}')
            current_run = None  # Reset for the next block of data

    return extracted_info


# Sample text mimicking the structure of your file
with open("madp_results.txt") as f:
    logs = f.read()

# Extracting the information
extracted_data = extract_information(logs)

with open("madp_results.csv", "w") as f:
    f.write("\n".join(extracted_data))



print(extracted_data)

