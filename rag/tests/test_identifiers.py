import re


def normalize_identifier(identifier):
    """
    Convert a programming identifier into
    human-readable words.
    """

    identifier = re.sub(
        r'([a-z0-9])([A-Z])',
        r'\1 \2',
        identifier
    )

    identifier = identifier.replace(
        "_",
        " "
    )

    identifier = identifier.replace(
        "-",
        " "
    )

    words = identifier.lower().split()

    return words


# Test identifiers

identifiers = [
    "FetchDataSourceQueryHandler",
    "DataSourceManager",
    "FetchDataSourceQuery",
    "getSource",
    "ContactSearchFields",
]


for identifier in identifiers:

    print(
        identifier,
        "→",
        normalize_identifier(identifier)
    )