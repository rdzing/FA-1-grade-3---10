import csv
import os
import json
import subprocess
import glob
import shutil

from src.core import AnswerRecognitionAndScoring

def process_image(image_path):
    # Create a temporary directory for processing
    temp_dir = "temp_inputs"
    os.makedirs(temp_dir, exist_ok=True)

    # Move the image to the temporary directory
    temp_image_path = os.path.join(temp_dir, os.path.basename(image_path))
    shutil.copy(image_path, temp_image_path)

    # Copy the template.json file to the temporary directory
    template_path = "inputs/template.json"
    if os.path.exists(template_path):
        shutil.copy(template_path, temp_dir)
    else:
        print("Error: template.json not found in the inputs directory.")
        return None

    # Copy the omr_marker.jpg file to the temporary directory
    marker_path = "inputs/omr_marker.jpg"
    if os.path.exists(marker_path):
        shutil.copy(marker_path, temp_dir)
    else:
        print("Error: omr_marker.jpg not found in the inputs directory.")
        return None

    try:
        # Run main.py with the temporary directory as input
        process = subprocess.run(["python", "main.py", "-i", temp_dir], capture_output=True, text=True)
        output = process.stdout

        # Log the full output for debugging
        print(f"Full output for {image_path}:\n{output}")

        # Extract JSON part from the output
        response_start = output.find("Read Response:")
        if response_start == -1:
            print(f"Error: 'Read Response:' not found for {image_path}.")
            return None

        response_raw = output[response_start + len("Read Response:"):].strip()
        start_index = response_raw.find("{")
        end_index = response_raw.rfind("}") + 1
        if start_index == -1 or end_index == -1:
            print(f"Error: Could not find JSON object in the output for {image_path}.")
            return None

        cleaned_response = response_raw[start_index:end_index].replace("'", '"')
        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse JSON for {image_path}.")
            print("Exception:", e)
            return None
    finally:
        # Clean up the temporary directory
        shutil.rmtree(temp_dir)

# Process all images in the inputs directory
image_paths = glob.glob("inputs/*.jpeg")
output_file = "outputs/final_scores.csv"

# Ensure the outputs directory exists
os.makedirs("outputs", exist_ok=True)

# Write header to the CSV file
with open(output_file, mode="w", newline="") as file:
    writer = csv.writer(file)
    header = ["Apaar_ID", "Exam_Code"]
    for i in range(1, 16):
        header.extend([f"Q{i}_recognized_answer", f"Q{i}_correct_answer", f"marks_for_Q{i}"])
    header.extend(["PART_D_recognition", "PART_D_marks", "Part_E_recognition", "Part_E_marks", "Total_marks"])
    writer.writerow(header)

# Process each image and append results to the CSV file
for image_path in image_paths:
    response = process_image(image_path)
    if not response:
        continue

    apaar_id = response.get("Apaar_ID", "N/A")
    exam_code = response.get("Exam_code", "N/A")
    recognized_answers = {int(k[1:]): v for k, v in response.items() if k.startswith('q')}
    part_d_recognition = response.get("PART_D", "")
    part_e_recognition = response.get("Part_E", "")

    part_d_marks = sum(int(d) for d in part_d_recognition if d.isdigit())
    part_e_marks = sum(int(d) for d in part_e_recognition if d.isdigit())

    scoring = AnswerRecognitionAndScoring()
    breakdown = scoring.calculate_scores(recognized_answers, list(map(int, part_d_recognition)), list(map(int, part_e_recognition)))

    row = [apaar_id, exam_code]
    total_marks = part_d_marks + part_e_marks

    for question_number in range(1, 16):
        recognized_answer = recognized_answers.get(question_number, "N/A")
        correct_answer = breakdown["details"].get(question_number, {}).get("correct_answer", "N/A")
        marks = breakdown["details"].get(question_number, {}).get("mark_allocated", 0)
        row.extend([recognized_answer, correct_answer, marks])
        total_marks += marks

    row.extend([part_d_recognition, part_d_marks, part_e_recognition, part_e_marks, total_marks])

    with open(output_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(row)

    print(f"Processed and saved results for {image_path}.")
