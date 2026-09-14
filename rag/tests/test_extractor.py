from php_extractor import extract_php_units


file_path = "../ushahidi/src/Ushahidi/Modules/V5/Actions/Datasource/Handlers/FetchDataSourceQueryHandler.php"


with open(file_path, "r", encoding="utf-8") as file:
    code = file.read()


units = extract_php_units(code)


print("Units found:", len(units))


for unit in units:

    print("\n" + "=" * 70)

    print("Namespace:", unit["namespace"])
    print("Class:", unit["class"])
    print("Method:", unit["method"])

    print("-" * 70)

    print(unit["content"])
    print("Calls:", unit["calls"])
    print(
    "Parameter types:",
    unit["parameter_types"]
    )
    print(
    "Property assignments:",
    unit["assignments"]
    )