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


count = 0

for file in REPO_PATH.rglob("*.php"):

    relative_path = file.relative_to(REPO_PATH)

    if relative_path.parts[0] not in INCLUDE_DIRS:
        continue

    code = file.read_text(
        encoding="utf-8",
        errors="ignore"
    )

    units = extract_php_units(code)

    for unit in units:

        print("\n" + "=" * 70)

        print("SOURCE:", relative_path)
        print("TYPE:", unit["type"])
        print("NAMESPACE:", unit["namespace"])
        print("CLASS:", unit["class"])
        print("METHOD:", unit["method"])

        print("-" * 70)

        print(unit["content"][:500])

        count += 1

        if count >= 10:
            break

    if count >= 10:
        break


print("\n" + "=" * 70)
print("SAMPLE UNITS:", count)
print("=" * 70)