from tree_sitter import Language, Parser
import tree_sitter_php


parser = Parser(
    Language(tree_sitter_php.language_php())
)


# Node types that declare a named type which can contain methods
TYPE_DECLARATIONS = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "trait_declaration": "trait",
    "enum_declaration": "enum",
}


def node_text(node, code_bytes):

    return code_bytes[
        node.start_byte:
        node.end_byte
    ].decode("utf-8", errors="ignore")


# ============================================================
# Extract Method Calls
# ============================================================

def extract_method_calls(node, code_bytes):

    calls = []

    def visit(current):

        if current.type in (
            "member_call_expression",
            "scoped_call_expression",
        ):

            object_node = (
                current.child_by_field_name("object")
                or current.child_by_field_name("scope")
            )
            name_node = current.child_by_field_name("name")

            calls.append({
                "object": node_text(object_node, code_bytes) if object_node else "",
                "method": node_text(name_node, code_bytes) if name_node else "",
            })

        for child in current.children:

            visit(child)

    visit(node)

    return calls


# ============================================================
# Extract Parameter Types
# ============================================================

def extract_parameter_types(node, code_bytes):

    parameters = {}

    def visit(current):

        if current.type in (
            "simple_parameter",
            "property_promotion_parameter",
        ):

            type_node = current.child_by_field_name("type")
            name_node = current.child_by_field_name("name")

            if type_node and name_node:

                parameters[node_text(name_node, code_bytes)] = node_text(
                    type_node, code_bytes
                )

        for child in current.children:

            visit(child)

    visit(node)

    return parameters


# ============================================================
# Extract Property Assignments
# ============================================================

def extract_property_assignments(node, code_bytes):

    assignments = []

    def visit(current):

        if current.type == "assignment_expression":

            left_node = current.child_by_field_name("left")
            right_node = current.child_by_field_name("right")

            assignments.append({
                "left": node_text(left_node, code_bytes) if left_node else "",
                "right": node_text(right_node, code_bytes) if right_node else "",
            })

        for child in current.children:

            visit(child)

    visit(node)

    return assignments


# ============================================================
# Build one unit (method or function)
# ============================================================

def build_unit(node, code_bytes, namespace, current_type, unit_type):

    name_node = node.child_by_field_name("name")

    body_node = node.child_by_field_name("body")

    modifiers = {
        child.type
        for child in node.children
    }

    type_name, type_kind = current_type or (None, None)

    return {

        "namespace": namespace,

        "class": type_name,

        "class_kind": type_kind,

        "method": node_text(name_node, code_bytes),

        "type": unit_type,

        # A method without a body is only a declaration
        # (interface method or abstract method)
        "abstract": (
            body_node is None
            or "abstract_modifier" in modifiers
        ),

        "start_line": node.start_point[0] + 1,

        "end_line": node.end_point[0] + 1,

        "content": node_text(node, code_bytes),

        "calls": extract_method_calls(node, code_bytes),

        "parameter_types": extract_parameter_types(node, code_bytes),

        "assignments": extract_property_assignments(node, code_bytes),

    }


# ============================================================
# Extract PHP Code Units
# ============================================================

def extract_php_units(code):
    """
    Split a PHP file into methods and functions.

    Files that contain no methods or functions (for example route
    files and config arrays) are returned as a single "file" unit,
    so they still end up in the vector database.
    """

    code_bytes = code.encode("utf-8")

    tree = parser.parse(code_bytes)

    namespace = None

    # --------------------------------------------------------
    # Extract Namespace
    # --------------------------------------------------------

    for node in tree.root_node.children:

        if node.type == "namespace_definition":

            namespace_node = node.child_by_field_name("name")

            if namespace_node:

                namespace = node_text(namespace_node, code_bytes)

            break

    units = []

    # --------------------------------------------------------
    # Traverse AST
    # --------------------------------------------------------

    def visit(node, current_type=None):

        # Class / Interface / Trait / Enum
        if node.type in TYPE_DECLARATIONS:

            name_node = node.child_by_field_name("name")

            if name_node:

                current_type = (
                    node_text(name_node, code_bytes),
                    TYPE_DECLARATIONS[node.type],
                )

        elif node.type == "anonymous_class":

            current_type = ("class@anonymous", "class")

        # Method
        if node.type == "method_declaration":

            if node.child_by_field_name("name"):

                units.append(build_unit(
                    node, code_bytes, namespace, current_type, "method"
                ))

        # Standalone Function
        elif node.type == "function_definition":

            if node.child_by_field_name("name"):

                units.append(build_unit(
                    node, code_bytes, namespace, None, "function"
                ))

        # Visit Children
        for child in node.children:

            visit(child, current_type)

    visit(tree.root_node)

    # --------------------------------------------------------
    # Fallback: whole file (routes, config, bootstrap)
    # --------------------------------------------------------

    if not units and code.strip():

        units.append({
            "namespace": namespace,
            "class": None,
            "class_kind": None,
            "method": None,
            "type": "file",
            "abstract": False,
            "start_line": 1,
            "end_line": code.count("\n") + 1,
            "content": code,
            "calls": extract_method_calls(tree.root_node, code_bytes),
            "parameter_types": {},
            "assignments": [],
        })

    return units
