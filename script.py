import os
import pathlib

REPO_PATH = "."  # ЗАМЕНИ на путь к твоему репо
MAX_FILE_SIZE_KB = 100  # Максимальный размер файла для загрузки в кб
INCLUDE_EXTENSIONS = [".py", ".sh", '.yml', '.bot', '.md']
EXCLUDE_NAMES = ["__init__"]


def print_tree(root_path):
    tree_lines = []
    for root, dirs, files in os.walk(root_path):
        # Удаляем скрытые директории (начинающиеся с точки)
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        level = root.replace(root_path, "").count(os.sep)
        indent = "  " * level
        if "pycache" not in os.path.basename(root):
            tree_lines.append(f"{indent}{os.path.basename(root)}/")
            subindent = "  " * (level + 1)
            for f in files:
                if "pyc" not in f:
                    tree_lines.append(f"{subindent}{f}")
    return "\n".join(tree_lines)

def is_hidden_path(path, root_path):
    rel_path = os.path.relpath(path, root_path)
    parts = rel_path.split(os.sep)
    if rel_path=='.':
        return False
    return any(part.startswith(".") for part in parts)


def collect_files(root_path, output_dir="family_bot"):
    os.makedirs(output_dir, exist_ok=True)
    output_dir_abs = os.path.abspath(output_dir)
    saved_files = []

    for root, dirs, files in os.walk(root_path):

        # Полный путь к текущей директории
        abs_root = os.path.abspath(root)

        # ❌ Пропускаем директории: скрытые или output_dir
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and os.path.abspath(os.path.join(root, d)) != output_dir_abs
        ]
        # ❌ Пропустить файлы в output_dir или скрытых путях
        if is_hidden_path(abs_root, root_path) or abs_root == output_dir_abs:
            continue
        for file in files:
            path = os.path.join(root, file)

            if is_hidden_path(path, root_path):
                continue

            if any(file.endswith(ext) for ext in INCLUDE_EXTENSIONS) and not any(
                file.startswith(ex) for ex in EXCLUDE_NAMES
            ):
                size_kb = pathlib.Path(path).stat().st_size / 1024
                if size_kb <= MAX_FILE_SIZE_KB:
                    rel_path = os.path.relpath(path, root_path)
                    target_path = os.path.join(output_dir, rel_path.replace("/", "__"))
                    target_path = target_path.replace(".py", ".txt")
                    target_path = target_path.replace(".sh", ".txt")
                    target_path = target_path.replace(".yml", ".txt")
                    target_path = target_path.replace(".bot", ".txt")
                    target_path = target_path.replace(".md", ".txt")
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with (
                        open(path, encoding="utf-8", errors="ignore") as fin,
                        open(target_path, "w", encoding="utf-8") as fout,
                    ):
                        fout.write(fin.read())
                    saved_files.append(target_path)
    return saved_files





if __name__ == "__main__":
    print("📂 Repository structure:")
    print(print_tree(REPO_PATH))

    print("\n📄 Extracting files for upload...")
    files = collect_files(REPO_PATH)
    print(
        f"✅ {len(files)} files saved to 'family_bot'. Загрузите их сюда по одному.",
    )
