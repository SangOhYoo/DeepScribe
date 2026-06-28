import os

app_data_dir = r"C:\Users\SangO\.gemini\antigravity"
for root, dirs, files in os.walk(app_data_dir):
    for file in files:
        if "ui.py" in file.lower():
            print(os.path.join(root, file))
