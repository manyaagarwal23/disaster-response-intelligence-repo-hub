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

    if node.type == "simple_parameter":

        type_node = node.child_by_field_name("type")
        name_node = node.child_by_field_name("name")

        parameter_type = ""
        parameter_name = ""

        if type_node:
            parameter_type = code[
                type_node.start_byte:
                type_node.end_byte
            ]

        if name_node:
            parameter_name = code[
                name_node.start_byte:
                name_node.end_byte
            ]

        print(
            "TYPE:",
            parameter_type
        )

        print(
            "PARAMETER:",
            parameter_name
        )

        print("-" * 50)

    for child in node.children:
        visit(child)


visit(tree.root_node)