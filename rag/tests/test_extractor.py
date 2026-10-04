from php_extractor import extract_php_units
import os

def test_extract_php_units():
    # Make sure we safely check if the file exists (to avoid crashing if ushahidi isn't cloned locally)
    file_path = "../ushahidi/src/Ushahidi/Modules/V5/Actions/Datasource/Handlers/FetchDataSourceQueryHandler.php"
    
    if not os.path.exists(file_path):
        print("Skipping test because Ushahidi repository is not cloned locally.")
        return

    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    units = extract_php_units(code)

    print("Units found:", len(units))
    
    # Standard pytest assertion
    assert len(units) > 0, "No PHP units were extracted from the file!"

    for unit in units:
        print("\n" + "=" * 70)
        print("Namespace:", unit["namespace"])
        print("Class:", unit["class"])
        print("Method:", unit["method"])
        print("-" * 70)
        print(unit["content"])
        print("Calls:", unit["calls"])
        print("Parameter types:", unit["parameter_types"])
        print("Property assignments:", unit["assignments"])