import os

IGNORE_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'env', 'node_modules', '.pytest_cache', 'build', 'dist'}
INCLUDE_EXTS = {'.py', '.sql', '.json', '.yaml', '.yml', '.toml', '.ini'}
OUTPUT_FILE = 'jarvis_full_codebase.txt'

def export_codebase():
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        out.write("# FULL JARVIS CODEBASE DUMP (LINE-BY-LINE)\n\n")
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in sorted(files):
                ext = os.path.splitext(file)[1].lower()
                if ext in INCLUDE_EXTS and file != OUTPUT_FILE and file != 'export_codebase.py':
                    filepath = os.path.join(root, file)
                    out.write("================================================================================\n")
                    out.write(f"FILE: {filepath}\n")
                    out.write("================================================================================\n")
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            for idx, line in enumerate(f, 1):
                                out.write(f"{idx:04d} | {line}")
                        out.write("\n\n")
                    except Exception as e:
                        out.write(f"[ERROR READING FILE: {e}]\n\n")

if __name__ == '__main__':
    export_codebase()
    print(f"Done! Created {OUTPUT_FILE} in {os.path.abspath(OUTPUT_FILE)}")
