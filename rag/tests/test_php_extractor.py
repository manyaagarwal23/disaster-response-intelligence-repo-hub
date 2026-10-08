from php_extractor import extract_php_units


def units_by_method(units):
    return {unit["method"]: unit for unit in units}


def test_interface_methods_get_interface_name(read_fixture):
    units = extract_php_units(read_fixture("src/Ushahidi/Contracts/EntityExists.php"))

    assert len(units) == 1
    unit = units[0]
    assert unit["namespace"] == "Ushahidi\\Contracts"
    assert unit["class"] == "EntityExists"
    assert unit["class_kind"] == "interface"
    assert unit["method"] == "exists"
    # Interface methods have no body: they are declarations only
    assert unit["abstract"] is True
    assert unit["parameter_types"] == {"$id": "int"}


def test_trait_methods_and_abstract_detection(read_fixture):
    units = units_by_method(extract_php_units(
        read_fixture("src/Ushahidi/Core/Usecase/Concerns/VerifyEntityLoaded.php")
    ))

    assert set(units) == {"getResourceName", "verifyEntityLoaded"}
    assert units["verifyEntityLoaded"]["class"] == "VerifyEntityLoaded"
    assert units["verifyEntityLoaded"]["class_kind"] == "trait"
    assert units["getResourceName"]["abstract"] is True
    # Implemented method mentions "NotFoundException" but is NOT abstract
    # (the old code used a substring check on the word "abstract")
    assert units["verifyEntityLoaded"]["abstract"] is False


def test_line_numbers_point_at_the_method(read_fixture):
    code = read_fixture("src/Ushahidi/Core/Usecase/Concerns/VerifyEntityLoaded.php")
    unit = units_by_method(extract_php_units(code))["verifyEntityLoaded"]

    lines = code.split("\n")
    assert "function verifyEntityLoaded" in lines[unit["start_line"] - 1]
    assert lines[unit["end_line"] - 1].strip() == "}"


def test_non_ascii_file_is_sliced_correctly(read_fixture):
    # The fixture has accented characters before the class. Slicing a str
    # with byte offsets would shift every method's text.
    units = units_by_method(extract_php_units(
        read_fixture("src/Ushahidi/DataSource/Twilio/TwilioController.php")
    ))

    assert units["handleRequest"]["content"].startswith("public function handleRequest")
    assert units["handleRequest"]["content"].endswith("}")


def test_calls_parameters_and_assignments(read_fixture):
    units = units_by_method(extract_php_units(
        read_fixture("src/Ushahidi/DataSource/Twilio/TwilioController.php")
    ))

    handle = units["handleRequest"]
    assert {"object": "$this->storage", "method": "receive"} in handle["calls"]
    assert {"object": "$request", "method": "input"} in handle["calls"]
    assert handle["parameter_types"] == {"$request": "Request"}
    assert {"left": "$from", "right": "$request->input('From')"} in handle["assignments"]

    # Constructor property promotion and static calls are captured too
    assert units["__construct"]["parameter_types"] == {"$storage": "DataSourceStorage"}
    assert {"object": "DataSourceStorage", "method": "instance"} in units["make"]["calls"]


def test_file_without_functions_becomes_a_file_unit(read_fixture):
    # Route files used to produce zero chunks and were never searchable
    units = extract_php_units(read_fixture("routes/api.php"))

    # The closure is not a named function, so the whole file is one unit
    assert len(units) == 1
    assert units[0]["type"] == "file"
    assert "PostController@store" in units[0]["content"]
    assert {"object": "$router", "method": "post"} in units[0]["calls"]


def test_standalone_function_and_anonymous_class():
    code = """<?php
function helper(string $name) { return strtoupper($name); }
$x = new class { public function run() { return 1; } };
"""
    units = units_by_method(extract_php_units(code))

    assert units["helper"]["type"] == "function"
    assert units["helper"]["class"] is None
    assert units["run"]["class"] == "class@anonymous"


def test_empty_file_produces_no_units():
    assert extract_php_units("") == []
