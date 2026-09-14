from tree_sitter import Language, Parser
import tree_sitter_php


file_path = r"..\ushahidi\src\Ushahidi\Modules\V5\Actions\Datasource\Handlers\FetchDataSourceQueryHandler.php"

code = open(
    file_path,
    encoding="utf-8"
).read()


parser = Parser(
    Language(tree_sitter_php.language_php())
)

tree = parser.parse(
    code.encode("utf-8")
)


def visit(node):

    if node.type == "member_call_expression":

        object_node = node.child_by_field_name("object")
        name_node = node.child_by_field_name("name")

        object_text = ""

        if object_node:
            object_text = code[
                object_node.start_byte:
                object_node.end_byte
            ]

        method_name = ""

        if name_node:
            method_name = code[
                name_node.start_byte:
                name_node.end_byte
            ]

        print(
            "OBJECT:",
            object_text
        )

        print(
            "METHOD:",
            method_name
        )

        print("-" * 50)

    for child in node.children:
        visit(child)


visit(tree.root_node)