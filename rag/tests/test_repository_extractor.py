from pathlib import Path

from php_extractor import extract_php_units


REPO_PATH = Path("../ushahidi")

INCLUDE_DIRS = {
    "src",
    "app",
    "config",
    "routes",
    "bootstrap",
}


php_files = []

for file in REPO_PATH.rglob("*.php"):

    relative_path = file.relative_to(REPO_PATH)

    if relative_path.parts[0] in INCLUDE_DIRS:

        php_files.append(file)


print("PHP files found:", len(php_files))


total_units = 0
files_with_units = 0
units_with_calls = 0
total_calls = 0


for file in php_files:

    try:

        code = file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        units = extract_php_units(code)

        if units:

            files_with_units += 1
            total_units += len(units)

            for unit in units:

                calls = unit["calls"]

                if calls:

                    units_with_calls += 1
                    total_calls += len(calls)

    except Exception as error:

        print(
            "Error:",
            file,
            error
        )


print("\n" + "=" * 60)
print("REPOSITORY EXTRACTION TEST")
print("=" * 60)

print("PHP files:", len(php_files))
print("Files containing units:", files_with_units)
print("Methods/functions extracted:", total_units)
print("Units containing calls:", units_with_calls)
print("Total method calls extracted:", total_calls)