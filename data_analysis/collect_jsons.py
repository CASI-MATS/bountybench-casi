import hashlib
import os
import shutil
import sys

def collect_jsons(src, dest):
    os.makedirs(dest, exist_ok=True)
    seen_names = set()
    seen_hashes = set()
    dup_count = 0

    for root, _, files in os.walk(src):
        for file in files:
            if file.lower().endswith(".json"):
                src_path = os.path.join(root, file)

                # Dedup by content hash (catches identical files with different names)
                with open(src_path, "rb") as fb:
                    content_hash = hashlib.sha256(fb.read()).hexdigest()
                if content_hash in seen_hashes:
                    dup_count += 1
                    print(f"Skipped (duplicate content): {src_path}")
                    continue
                seen_hashes.add(content_hash)

                # Resolve filename collisions by appending a suffix
                dest_name = file
                if dest_name in seen_names:
                    base, ext = os.path.splitext(dest_name)
                    counter = 1
                    while dest_name in seen_names:
                        dest_name = f"{base}_{counter}{ext}"
                        counter += 1
                seen_names.add(dest_name)

                dest_path = os.path.join(dest, dest_name)
                shutil.copy(src_path, dest_path)
                print(f"Copied: {src_path} -> {dest_path}")

    if dup_count:
        print(f"\nSkipped {dup_count} duplicate file(s) by content hash")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python collect_jsons.py C:/Users/ivanz/Desktop/bountybench-runner/results C:/Users/ivanz/Desktop/bountybench-runner/logs")
        sys.exit(1)

    collect_jsons(sys.argv[1], sys.argv[2])
