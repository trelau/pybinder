import os


def find_include_path(name, path):
    """
    Attempt to find an include directory of a given header file.

    :param name: The header file to search for.
    :param path: The starting path.

    :return: The full path to the directory of the given header file.
    """
    for root, dirs, files in os.walk(path):
        if name in files:
            return root


def get_includes_for_cursors(cursors):
    """
    Gather all the include files for a list of cursors.

    :param list[pybinder.clang.generator.CursorWrapper] cursors:

    :return:
    """
    module_includes = []
    fwd_includes = []

    # Includes for the cursors themselves
    for cursor in cursors:
        header = cursor.source_file
        if header in module_includes:
            continue
        module_includes.append(header)

    # Include for forward declared types found by walking the cursor
    for cursor in cursors:
        for c in cursor.walk_preorder():
            # Only find type references
            if not c.is_type_ref:
                continue
            d = c.get_definition()
            if not d.is_definition:
                continue

            # Get the header if not already included
            header = d.source_file
            if header in fwd_includes or header in module_includes:
                continue
            fwd_includes.append(header)

    return module_includes, fwd_includes
