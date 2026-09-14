from tree_sitter import Language, Parser
import tree_sitter_php


# ============================================================
# 1. Load PHP Parser
# ============================================================

parser = Parser(
    Language(tree_sitter_php.language_php())
)


# ============================================================
# 2. Read Test File
# ============================================================

file_path = "../ushahidi/src/Ushahidi/Modules/V5/Actions/Datasource/Handlers/FetchDataSourceQueryHandler.php"

with open(file_path, "r", encoding="utf-8") as file:
    code = file.read()


# ============================================================
# 3. Parse PHP Code
# ============================================================

tree = parser.parse(
    code.encode("utf-8")
)


# ============================================================
# 4. Extract Namespace
# ============================================================

namespace = None

for node in tree.root_node.children:

    if node.type == "namespace_definition":

        namespace_node = node.child_by_field_name("name")

        if namespace_node:
            namespace = code[
                namespace_node.start_byte:
                namespace_node.end_byte
            ]

        break


# ============================================================
# 5. Find Class and Methods
# ============================================================

def find_class(node):

    if node.type == "class_declaration":

        class_name_node = node.child_by_field_name("name")

        class_name = code[
            class_name_node.start_byte:
            class_name_node.end_byte
        ]

        print("\n" + "=" * 70)
        print("CLASS:", class_name)
        print("NAMESPACE:", namespace)
        print("=" * 70)

        for child in node.children:

            if child.type != "declaration_list":
                continue

            for method in child.children:

                if method.type == "method_declaration":

                    method_name_node = method.child_by_field_name("name")

                    method_name = code[
                        method_name_node.start_byte:
                        method_name_node.end_byte
                    ]

                    method_code = code[
                        method.start_byte:
                        method.end_byte
                    ]

                    print("\n" + "-" * 70)
                    print("METHOD:", method_name)
                    print("-" * 70)

                    print(method_code)

    for child in node.children:
        find_class(child)


find_class(tree.root_node)