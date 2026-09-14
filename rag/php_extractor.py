from tree_sitter import Language, Parser
import tree_sitter_php


parser = Parser(
    Language(tree_sitter_php.language_php())
)


# ============================================================
# Extract Method Calls
# ============================================================

def extract_method_calls(node, code):

    calls = []

    def visit(current):

        if current.type == "member_call_expression":

            object_node = current.child_by_field_name("object")
            name_node = current.child_by_field_name("name")

            object_text = ""
            method_name = ""

            if object_node:

                object_text = code[
                    object_node.start_byte:
                    object_node.end_byte
                ]

            if name_node:

                method_name = code[
                    name_node.start_byte:
                    name_node.end_byte
                ]

            calls.append({
                "object": object_text,
                "method": method_name
            })

        for child in current.children:

            visit(child)

    visit(node)

    return calls


# ============================================================
# Extract Parameter Types
# ============================================================

def extract_parameter_types(node, code):

    parameters = {}

    def visit(current):

        if current.type == "simple_parameter":

            type_node = current.child_by_field_name("type")
            name_node = current.child_by_field_name("name")

            if type_node and name_node:

                parameter_type = code[
                    type_node.start_byte:
                    type_node.end_byte
                ]

                parameter_name = code[
                    name_node.start_byte:
                    name_node.end_byte
                ]

                parameters[parameter_name] = parameter_type

        for child in current.children:

            visit(child)

    visit(node)

    return parameters


# ============================================================
# Extract Property Assignments
# ============================================================

def extract_property_assignments(node, code):

    assignments = []

    def visit(current):

        if current.type == "assignment_expression":

            left_node = current.child_by_field_name("left")
            right_node = current.child_by_field_name("right")

            left_text = ""
            right_text = ""

            if left_node:

                left_text = code[
                    left_node.start_byte:
                    left_node.end_byte
                ]

            if right_node:

                right_text = code[
                    right_node.start_byte:
                    right_node.end_byte
                ]

            assignments.append({
                "left": left_text,
                "right": right_text
            })

        for child in current.children:

            visit(child)

    visit(node)

    return assignments


# ============================================================
# Extract PHP Code Units
# ============================================================

def extract_php_units(code):

    tree = parser.parse(
        code.encode("utf-8")
    )

    namespace = None

    # --------------------------------------------------------
    # Extract Namespace
    # --------------------------------------------------------

    for node in tree.root_node.children:

        if node.type == "namespace_definition":

            namespace_node = node.child_by_field_name("name")

            if namespace_node:

                namespace = code[
                    namespace_node.start_byte:
                    namespace_node.end_byte
                ]

            break


    units = []


    # --------------------------------------------------------
    # Traverse AST
    # --------------------------------------------------------

    def visit(node, current_class=None):

        # ====================================================
        # Class
        # ====================================================

        if node.type == "class_declaration":

            class_name_node = node.child_by_field_name("name")

            if class_name_node:

                current_class = code[
                    class_name_node.start_byte:
                    class_name_node.end_byte
                ]


        # ====================================================
        # Method
        # ====================================================

        if node.type == "method_declaration":

            method_name_node = node.child_by_field_name("name")

            if method_name_node:

                method_name = code[
                    method_name_node.start_byte:
                    method_name_node.end_byte
                ]

                method_code = code[
                    node.start_byte:
                    node.end_byte
                ]

                calls = extract_method_calls(
                    node,
                    code
                )

                parameter_types = extract_parameter_types(
                    node,
                    code
                )

                assignments = extract_property_assignments(
                    node,
                    code
                )

                units.append({

                    "namespace": namespace,

                    "class": current_class,

                    "method": method_name,

                    "type": "method",

                    "content": method_code,

                    "calls": calls,

                    "parameter_types": parameter_types,

                    "assignments": assignments

                })


        # ====================================================
        # Standalone Function
        # ====================================================

        elif node.type == "function_definition":

            function_name_node = node.child_by_field_name("name")

            if function_name_node:

                function_name = code[
                    function_name_node.start_byte:
                    function_name_node.end_byte
                ]

                function_code = code[
                    node.start_byte:
                    node.end_byte
                ]

                calls = extract_method_calls(
                    node,
                    code
                )

                parameter_types = extract_parameter_types(
                    node,
                    code
                )

                assignments = extract_property_assignments(
                    node,
                    code
                )

                units.append({

                    "namespace": namespace,

                    "class": None,

                    "method": function_name,

                    "type": "function",

                    "content": function_code,

                    "calls": calls,

                    "parameter_types": parameter_types,

                    "assignments": assignments

                })


        # ====================================================
        # Visit Children
        # ====================================================

        for child in node.children:

            visit(
                child,
                current_class
            )


    visit(tree.root_node)

    return units