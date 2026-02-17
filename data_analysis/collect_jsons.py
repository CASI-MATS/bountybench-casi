import os
import shutil
import sys

def collect_jsons(src, dest):
    os.makedirs(dest, exist_ok=True)
    seen = set()

    for root, _, files in os.walk(src):
        for file in files:
            if file.lower().endswith(".json"):
                if file not in seen:
                    seen.add(file)
                    src_path = os.path.join(root, file)
                    dest_path = os.path.join(dest, file)
                    shutil.copy(src_path, dest_path)
                    print(f"Moved: {src_path} -> {dest_path}")
                else:
                    print(f"Skipped (duplicate): {os.path.join(root, file)}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python collect_jsons.py C:/Users/ivanz/Desktop/bountybench-runner/results C:/Users/ivanz/Desktop/bountybench-runner/logs")
        sys.exit(1)

    collect_jsons(sys.argv[1], sys.argv[2])
