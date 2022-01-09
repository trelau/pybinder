import operator
import os
import shutil
from collections import defaultdict

from pybinder.bind import bind_enum, bind_class, bind_class_template, bind_typedef, bind_function
from pybinder.utilities import get_includes_for_cursors
from pybinder.wrap import (wrap_class_cursor, wrap_enum_cursor, wrap_function_cursor,
                           wrap_typedef_cursor, wrap_class_template_cursor)

__all__ = ['generate_bindings']


# TODO Multiple inheritance
# TODO Trampoline classes
# TODO Error handlers


def generate_bindings(parser, config, path, remove=False):
    """

    :param pybinder.parse.Parser parser:
    :param pybinder.configure.Configurator config:
    :param path:
    :param remove:
    :return:
    """
    # Remove source contents
    if remove and os.path.exists(path):
        shutil.rmtree(path)
        os.mkdir(path)

    # ============================================================================================ #
    # Wrap
    # ============================================================================================ #
    available_modules = set()
    module_enums = defaultdict(list)
    module_functions = defaultdict(list)
    module_types = defaultdict(list)

    ordered_classes = list()
    ordered_typedefs = list()
    ordered_types = list()

    registered_classes = dict()
    registered_typedefs = dict()
    registered_templates = dict()
    canonical_types = dict()

    for cursor in parser.get_children():
        # Only enums, functions, classes, typedefs, or templates
        if not (cursor.is_enum_decl or cursor.is_function_decl or cursor.is_class_decl or
                cursor.is_struct_decl or cursor.is_typedef_decl or cursor.is_class_template_decl):
            continue

        # Definitions only
        if not cursor.is_definition:
            continue

        # Ignore cursors in unavailable headers
        header = cursor.source_file
        if not config.is_available_header(header):
            continue

        # Assume the module is the first part of the source header
        mod = header.replace('.', '_').split('_', maxsplit=1)[0]
        if config.is_excluded_module(mod):
            continue

        # Enums
        if cursor.is_enum_decl:
            enum = wrap_enum_cursor(cursor)
            enum.module_name = mod
            module_enums[mod].append(enum)
            available_modules.add(mod)

        # Functions
        elif cursor.is_function_decl:
            func = wrap_function_cursor(cursor)
            func.module_name = mod

            if config.is_excluded_function(mod, func.register_name):
                func.is_excluded = True

            module_functions[mod].append(func)
            available_modules.add(mod)

        # Classes
        elif cursor.is_class_decl or cursor.is_struct_decl:
            klass = wrap_class_cursor(cursor)
            klass.module_name = mod

            if config.is_excluded_class(mod, klass.register_name):
                klass.is_excluded = True

            module_types[mod].append(klass)
            available_modules.add(mod)

            ordered_classes.append(klass)
            ordered_types.append(klass)
            registered_classes[klass.register_name] = klass

            canonical_types[klass.canonical_type_name] = klass

            for nklass in klass.nested_classes:
                nklass.module_name = mod
                if config.is_excluded_class(mod, nklass.register_name):
                    nklass.is_excluded = True

                ordered_classes.append(klass)
                registered_classes[nklass.register_name] = nklass

                canonical_types[nklass.canonical_type_name] = nklass

            for ntemplate in klass.nested_class_templates:
                ntemplate.module_name = mod
                if config.is_excluded_class(mod, ntemplate.register_name):
                    ntemplate.is_excluded = True

                registered_templates[ntemplate.register_name] = ntemplate

        # Typedefs
        elif cursor.is_typedef_decl:
            typedef = wrap_typedef_cursor(cursor)
            typedef.module_name = mod

            if config.is_excluded_typedef(mod, typedef.register_name):
                typedef.is_excluded = True

            module_types[mod].append(typedef)
            available_modules.add(mod)

            ordered_typedefs.append(typedef)
            ordered_types.append(typedef)
            registered_typedefs[typedef.register_name] = typedef

        # Class templates
        elif cursor.is_class_template_decl:
            template = wrap_class_template_cursor(cursor)
            template.module_name = mod
            registered_templates[template.register_name] = template
            if config.is_excluded_class(mod, template.register_name):
                template.is_excluded = True

            for ntemplate in template.nested_class_templates:
                ntemplate.module_name = mod
                registered_templates[ntemplate.register_name] = ntemplate
                if config.is_excluded_class(mod, ntemplate.register_name):
                    ntemplate.is_excluded = True

            for nklass in template.klass.nested_classes:
                nklass.module_name = mod
                if config.is_excluded_class(mod, nklass.register_name):
                    nklass.is_excluded = True

    # ============================================================================================ #
    # Process
    # ============================================================================================ #
    # Go through the ordered types and find typedef aliases
    for typedef in ordered_typedefs:
        if typedef.canonical_type_name in canonical_types:
            typedef.is_alias = True
            other = canonical_types[typedef.canonical_type_name]
            typedef.alias = other
            msg = 'Alias: {} --> {}'.format(typedef, other)
            print(msg)
        else:
            typedef.is_alias = False
            canonical_types[typedef.canonical_type_name] = typedef

    # Map typedefs to an available template if applicable. If a template is not available then
    # exclude the typedef from later processing.
    for typedef in ordered_typedefs:
        if typedef.is_excluded:
            continue
        if typedef.is_templated and typedef.underlying_template_name in registered_templates:
            template = registered_templates[typedef.underlying_template_name]
            if template.is_excluded:
                typedef.is_excluded = True
            else:
                typedef.function_name = template.function_name
                typedef.extra_includes.append(template.source_name)
        else:
            typedef.is_excluded = True
            if typedef.is_templated:
                msg = 'Excluding typedef {} (unavailable template: {})'.format(
                    typedef.register_name,
                    typedef.underlying_template_name)
            else:
                msg = 'Excluding typedef {} (unsupported type)'.format(typedef.register_name)
            print(msg)

    # Loop through all base classes and mark them if they are available. While doing this check
    # for base classes that could be registered via a template.
    for klass in ordered_classes:
        if klass.is_excluded:
            continue
        for base in klass.bases:
            if base.is_class and base.referenced_name in registered_classes:
                superclass = registered_classes[base.referenced_name]
                if not superclass.is_excluded:
                    base.is_excluded = False
                    base.superclass = superclass
            elif base.is_typedef and base.referenced_name in registered_typedefs:
                superclass = registered_typedefs[base.referenced_name]
                if not superclass.is_excluded:
                    base.is_excluded = False
                    base.superclass = superclass
            elif base.is_templated and base.referenced_template in registered_templates:
                superclass = registered_templates[base.referenced_template]
                if not superclass.is_excluded:
                    base.is_excluded = False
                    base.template = superclass
                    klass.extra_bases.insert(0, base)
                    klass.extra_includes.append(superclass.source_name)
            else:
                msg = 'Excluding base {} of {}'.format(base, klass)
                print(msg)

    # Loop through all template base classes and mark them if they are available
    for name in registered_templates:
        template = registered_templates[name]
        if template.is_excluded:
            continue
        for base in template.klass.bases:
            if base.is_template_param_base:
                base.is_excluded = False
            elif base.is_class and base.referenced_name in registered_classes:
                superclass = registered_classes[base.referenced_name]
                if not superclass.is_excluded:
                    base.is_excluded = False
                    base.superclass = superclass
            elif base.is_typedef and base.referenced_name in registered_typedefs:
                superclass = registered_typedefs[base.referenced_name]
                if not superclass.is_excluded:
                    base.is_excluded = False
                    base.superclass = superclass
            elif (base.is_templated or base.is_template) and base.referenced_template in registered_templates:
                superclass = registered_templates[base.referenced_template]
                if not superclass.is_excluded:
                    base.is_excluded = False
                    base.template = superclass
                    template.klass.extra_bases.insert(0, base)
                    template.extra_includes.append(superclass.source_name)
            else:
                msg = 'Excluding template base {} in {}'.format(base, template)
                print(msg)

    # Set opencascade::handle holder types for classes that need it
    for klass in ordered_classes:
        if klass.register_name == 'Standard_Transient':
            klass.holder_type = 'opencascade::handle'
        elif klass.is_derived_from('Standard_Transient'):
            klass.holder_type = 'opencascade::handle'
        for nklass in klass.nested_classes:
            nklass.holder_type = klass.holder_type
        for ntemplate in klass.nested_class_templates:
            ntemplate.klass.holder_type = klass.holder_type

    # Set opencascade::handle holder types for templates that need it
    for name in registered_templates:
        template = registered_templates[name]
        if template.klass.is_derived_from('Standard_Transient'):
            template.klass.holder_type = 'opencascade::handle'
        for nklass in template.klass.nested_classes:
            nklass.holder_type = template.klass.holder_type

    # ============================================================================================ #
    # Bind
    # ============================================================================================ #
    # Bind templates
    for name in registered_templates:
        template = registered_templates[name]
        # Skip nested classes in templates but bind templates defined in a class
        if template.is_nested and not template.is_class_template_decl:
            continue
        bind_class_template(path, template, config)

    # Bind modules
    for mod in available_modules:
        enums = module_enums[mod]
        funcs = module_functions[mod]
        types = module_types[mod]
        generate_module('./src', mod, enums, funcs, types, config)

    # Open the main file
    main_fout = open('./src/{}.cxx'.format('OCCT'), 'w')

    # Write preamble content
    main_fout.write(config.preamble)

    # Common headers
    if config.common_headers:
        main_fout.write('// Common headers\n')
        for h in config.common_headers:
            main_fout.write('#include <{}>\n'.format(h))
        main_fout.write('\n')

    # Sort the available modules to make process deterministic
    submodules = sorted(list(available_modules))

    # Bind interface for enums
    main_fout.write('// Enums\n')
    for mod in submodules:
        main_fout.write('void bind_{}_enums(py::module&);\n'.format(mod))

    # Bind interface for functions
    main_fout.write('// Functions\n')
    for mod in submodules:
        main_fout.write('void bind_{}_functions(py::module&);\n'.format(mod))

    # Bind interface for types
    main_fout.write('// Types\n')
    for type_ in ordered_types:
        if type_.is_excluded or type_.is_nested or type_.is_alias:
            continue
        main_fout.write('void bind_{}(py::module&);\n'.format(type_.python_name))

    # Module definition
    main_fout.write('\nPYBIND11_MODULE({}, main) {{\n\n'.format('OCCT'))

    # Register the submodules
    main_fout.write('// Submodules\n')
    for smod in submodules:
        doc = 'The {} module.'.format(smod)
        txt = 'main.def_submodule(\"{}\", \"{}\");\n'.format(smod, doc)
        main_fout.write(txt)
    main_fout.write('\n')

    # Bind enums
    main_fout.write('// Enums\n')
    for mod in submodules:
        main_fout.write('bind_{}_enums(main);\n'.format(mod))

    # Bind functions
    main_fout.write('// Functions\n')
    for mod in submodules:
        main_fout.write('bind_{}_functions(main);\n'.format(mod))

    # Bind types
    main_fout.write('// Types\n')
    for type_ in ordered_types:
        if type_.is_excluded or type_.is_nested or type_.is_alias:
            continue
        main_fout.write('bind_{}(main);\n'.format(type_.python_name))

    # Aliases
    main_fout.write('// Aliases\n')
    for typedef in ordered_typedefs:
        if typedef.is_excluded or not typedef.is_alias:
            continue
        other = typedef.alias
        if other.is_excluded:
            continue
        # Hack until OCCT fixes missing include guard...
        if typedef.python_name == 'BRepExtrema_MapOfIntegerPackedMapOfInteger':
            continue
        txt = 'main.attr(\"{}\").attr(\"{}\") = main.attr(\"{}\").attr(\"{}\");\n'.format(
            typedef.module_name,
            typedef.python_name,
            other.module_name,
            other.python_name)
        main_fout.write(txt)

    main_fout.write('\n}\n')
    main_fout.close()


def generate_module(output_dir, name, enums, functions, types, config):
    """

    :param output_dir:
    :param name:
    :param list(pybinder.wrap.EnumWrapper) enums:
    :param list(pybinder.wrap.FunctionWrapper) functions:
    :param list(pybinder.wrap.ClassWrapper) types:
    :param config:

    :return:
    """
    fname = '.'.join([name, 'cxx'])
    fdir = '/'.join([output_dir, fname])

    fout = open(fdir, 'w')

    # Preamble
    fout.write(config.preamble)

    # Common includes
    if config.common_headers:
        fout.write('// Common includes\n')
        for h in config.common_headers:
            fout.write('#include <{}>\n'.format(h))
        fout.write('\n')

    # Extra includes
    extra_includes = config.get_extra_headers(name)
    if extra_includes:
        fout.write('// Manually specified includes\n')
        for h in extra_includes:
            fout.write('#include <{}>\n'.format(h))
        fout.write('\n')

    # Process the headers for cursors in the module
    cursors = enums + functions + types
    module_includes, fwd_includes = get_includes_for_cursors(cursors)

    # Include only ones that are available
    module_includes = [h for h in module_includes if config.is_available_header(h)]
    fwd_includes = [h for h in fwd_includes if config.is_available_header(h)]

    # TODO Forward declared type includes
    fwd_includes = []
    if fwd_includes:
        fout.write('// Includes for needed types\n')
        for h in fwd_includes:
            fout.write('#include <{}>\n'.format(h))
        fout.write('\n')

    # Includes for module content
    fout.write('// Module includes\n')
    for h in module_includes:
        fout.write('#include <{}>\n'.format(h))
    fout.write('\n')

    # Extra includes
    extra_includes = set()
    for cursor in types:
        for h in cursor.extra_includes:
            extra_includes.add(h)
        if not cursor.is_typedef_decl:
            for nklass in cursor.nested_classes:
                for h in nklass.extra_includes:
                    extra_includes.add(h)
    if extra_includes:
        fout.write('// Extra includes\n')
        for h in extra_includes:
            fout.write('#include <{}>\n'.format(h))
        fout.write('\n')

    # Bind enums
    txt = 'void bind_{}_enums(py::module &main){{\n\n'.format(name)
    fout.write(txt)
    txt = 'py::module mod = main.attr(\"{}\");\n\n'.format(name)
    fout.write(txt)
    for enum in enums:
        bind_enum(enum, fout)
    fout.write('}\n\n')

    # Bind functions
    txt = 'void bind_{}_functions(py::module &main){{\n\n'.format(name)
    fout.write(txt)
    txt = 'py::module mod = main.attr(\"{}\");\n\n'.format(name)
    fout.write(txt)
    functions = [(f.register_name, f) for f in functions]
    functions.sort(key=operator.itemgetter(0))
    for _, func in functions:
        bind_function(func, fout)
    fout.write('}\n\n')

    # Bind types
    for type_ in types:
        if type_.is_class_decl or type_.is_struct_decl:
            bind_class(type_, fout)
        elif type_.is_typedef_decl:
            bind_typedef(type_, fout)

    # Close module file
    fout.close()
