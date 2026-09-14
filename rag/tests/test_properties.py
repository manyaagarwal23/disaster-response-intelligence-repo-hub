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

    if node.type == "assignment_expression":

        left_node = node.child_by_field_name("left")
        right_node = node.child_by_field_name("right")

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

        print(
            "LEFT:",
            left_text
        )

        print(
            "RIGHT:",
            right_text
        )

        print("-" * 50)

    for child in node.children:

        visit(child)


visit(tree.root_node)