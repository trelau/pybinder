def bind_function(func, fout):
    """

    :param pybinder.wrap.FunctionWrapper func:
    :param fout:

    :return:
    """

    if func.is_excluded:
        return

    # Write source label
    line1 = '// ' + 93 * '=' + ' //\n'
    line2 = '// Function: {}\n'.format(func.register_name)
    line3 = '// Source: {}\n'.format(func.header_file)
    line4 = '// ' + 93 * '=' + ' //\n'
    label = line1 + line2 + line3 + line4
    fout.write(label)

    # Function
    fout.write('{}.def(\"{}\",\n'.format(func.container, func.python_name))

    # Parameters
    params = ', '.join([p.register_name for p in func.parameters])
    args = ', '.join(['py::arg(\"{}\")'.format(p.python_name) for p in func.parameters])

    # Signature
    txt = '     ({} (*) ({})) &{},\n'.format(func.result_name, params, func.register_name)
    fout.write(txt)

    # Docs
    txt = '     R\"({})\"'.format(func.docs)
    fout.write(txt)

    # Write arguments
    if args:
        fout.write(',\n')
        fout.write('     {});\n\n'.format(args))
    else:
        fout.write(');\n\n')


def bind_enum(enum, fout):
    """

    :param pybinder.wrap.EnumWrapper enum:
    :param TextIO fout:

    :return:
    """
    if enum.is_excluded:
        return

    # Write source label
    if enum.is_nested:
        label = '// Nested enum: {}\n'.format(enum.register_name)
    else:
        line1 = '// ' + 93 * '=' + ' //\n'
        if enum.is_anonymous:
            line2 = '// Anonymous Enum\n'
        else:
            line2 = '// Enum: {}\n'.format(enum.register_name)
        line3 = '// Source: {}\n'.format(enum.header_file)
        line4 = '// ' + 93 * '=' + ' //\n'
        label = line1 + line2 + line3 + line4
    fout.write(label)

    # Bind anonymous enums as integers (special case)
    if enum.is_anonymous:
        for ec in enum.constants:
            txt = '{}.attr(\"{}\") = py::cast(int({}));\n'.format(enum.container,
                                                                  ec.python_name,
                                                                  ec.register_name)
            fout.write(txt)
        fout.write('\n')
        return

    # Normal enum
    txt = 'py::enum_<{}>({}, \"{}\", R\"({})\")\n'.format(enum.register_name,
                                                          enum.container,
                                                          enum.python_name,
                                                          enum.docs)
    fout.write(txt)
    for ec in enum.constants:
        txt = '\t.value(\"{}\", {})\n'.format(ec.python_name, ec.register_name)
        fout.write(txt)
    fout.write('\t.export_values();\n\n')


def bind_class(klass, fout, config):
    """

    :param pybinder.wrap.ClassWrapper klass:
    :param fout:
    :param pybinder.configure.Configurator config:

    :return:
    """
    if klass.is_excluded:
        return

    # Write source label
    if klass.is_nested:
        label = '// Nested class: {}\n'.format(klass.register_name)
    elif klass.is_template or klass.is_alias:
        label = ''
    else:
        line1 = '// ' + 93 * '=' + ' //\n'
        line2 = '// Class: {}\n'.format(klass.register_name)
        line3 = '// Source: {}\n'.format(klass.header_file)
        line4 = '// ' + 93 * '=' + ' //\n'
        label = line1 + line2 + line3 + line4
    fout.write(label)

    # Function
    if not klass.is_nested and not klass.is_template and not klass.is_alias:
        txt = 'void bind_{}(py::module &main){{\n\n'.format(klass.python_name)
        fout.write(txt)

    # Before
    before = config.get_class_before(klass.register_name)
    if before:
        fout.write('// Before\n')
        for line in before:
            fout.write(line)
            fout.write('\n')
        fout.write('\n')

    # Get the module
    if not klass.is_nested and not klass.is_template and not klass.is_alias:
        txt = 'py::module mod = main.attr(\"{}\");\n'.format(klass.module_name)
        fout.write(txt)

    # Register name to handle bases
    if klass.is_template and not klass.is_nested:
        fout.write('// Register name\n')
        fout.write('std::string register_name;\n')
        fout.write('if (is_base) {\n')
        fout.write('\tregister_name = name + \"_{}\";\n'.format(klass.python_name))
        fout.write('} else {\n')
        fout.write('\tregister_name = name;\n')
        fout.write('}\n\n')

    # Skip is type already registered
    if klass.is_template and not klass.is_nested:
        fout.write('// Skip if a base class is already registered\n')
        txt = 'if (py::detail::get_type_handle(typeid({}), false) && is_base) {{\n'.format(
            klass.register_name)
        fout.write(txt)
        # fout.write('\tstd::cout << "-- Skipping base type: \" << register_name << \"\\n\";\n')
        fout.write('\treturn;\n')
        fout.write('}\n\n')

    # Register bases if needed
    for base in klass.extra_bases:
        fout.write('// Register base: {}\n'.format(base.referenced_name))
        if base.is_template:
            name = 'name'
        elif base.is_templated:
            name = '\"{}\"'.format(klass.python_name)
        else:
            raise RuntimeError('Unknown base {}'.format(base.referenced_name))

        txt = '{}{}(mod, {}, true);\n'.format(base.template.function_name, base.parameters, name)
        fout.write(txt)
        fout.write('\n')

    # Handle
    handle = '{}<{}>'.format(klass.handle, klass.register_name)

    # Bases
    bases = ', '.join([b.base_name for b in klass.bases if not b.is_excluded])
    if bases:
        bases = ', ' + bases

    # Python name is function input for a class template
    if klass.is_template and not klass.is_nested:
        python_name = 'register_name.c_str()'
    else:
        python_name = '\"' + klass.python_name + '\"'

    if klass.is_nested:
        is_local = ', py::module_local()'
    else:
        is_local = ''
    fout.write('py::class_<{}, {}{}>'.format(klass.register_name, handle, bases))
    fout.write('{}({}, {}, R\"({})\"{});\n'.format(klass.object_name, klass.container,
                                                   python_name, klass.docs, is_local))

    # Constructors
    # TODO Abstract types
    if not klass.is_abstract:
        fout.write('\n// Constructors\n')
        for ctor in klass.constructors:
            bind_constructor(ctor, fout)

    # Method
    fout.write('\n// Methods\n')
    for method in klass.methods:
        bind_method(klass, method, fout)

    # Iterator
    if klass.is_iterator:
        bind_class_iterator(klass, fout)

    # Nested enums
    if klass.nested_enums:
        fout.write('\n')
    for enum in klass.nested_enums:
        bind_enum(enum, fout)

    # Nested classes
    if klass.nested_classes:
        fout.write('\n')
    for nklass in klass.nested_classes:
        bind_class(nklass, fout, config)

    if not klass.is_nested:
        fout.write('\n')
        fout.write('}\n\n')


def bind_typedef(typedef, fout):
    """

    :param pybinder.wrap.TypedefWrapper typedef:
    :param fout:
    :return:
    """
    if typedef.is_excluded or typedef.is_alias:
        return

    # Write source label
    line1 = '// ' + 93 * '=' + ' //\n'
    line2 = '// Typedef: {}\n'.format(typedef.register_name)
    line3 = '// Source: {}\n'.format(typedef.header_file)
    line4 = '// ' + 93 * '=' + ' //\n'
    label = line1 + line2 + line3 + line4
    fout.write(label)

    # Function
    txt = 'void bind_{}(py::module &main){{\n\n'.format(typedef.python_name)
    fout.write(txt)

    # Get the module
    txt = 'py::module mod = main.attr(\"{}\");\n'.format(typedef.module_name)
    fout.write(txt)

    if not typedef.is_templated:
        msg = 'Non-templated typedef encountered: {}'.format(typedef.register_name)
        raise RuntimeError(msg)

    txt = '{}{}({}, \"{}\");\n'.format(typedef.function_name, typedef.parameters,
                                       typedef.container, typedef.python_name)
    fout.write(txt)
    fout.write('\n')
    fout.write('}\n\n')


def bind_class_template(output_dir, template, config):
    """

    :param output_dir:
    :param pybinder.wrap.ClassTemplateWrapper template:
    :param config:

    :return:
    """
    if template.is_excluded:
        return

    # Open a new file for writing
    fdir = '/'.join([output_dir, template.source_name])
    fout = open(fdir, 'w')

    # Preamble
    fout.write(config.preamble)

    # Include guard
    fout.write('#pragma once\n\n')

    # Common headers
    if config.common_headers:
        fout.write('// Common headers\n')
        for h in config.common_headers:
            fout.write('#include <{}>\n'.format(h))
        fout.write('\n')

    # Headers for this template
    fout.write(' // Headers for this template\n')
    fout.write('#include <{}>\n\n'.format(template.header_file))

    # Extra includes
    if template.extra_includes:
        fout.write('// Extra includes\n')
        for h in template.extra_includes:
            fout.write('#include <{}>\n'.format(h))
        fout.write('\n')

    bind_template(template, fout, config)

    fout.close()


def bind_template(template, fout, config):
    """

    :param pybinder.wrap.ClassTemplateWrapper template:
    :param fout:
    :return:
    """
    if template.is_excluded:
        return

    # Write source label
    line1 = '// ' + 93 * '=' + ' //\n'
    line2 = '// Template: {}\n'.format(template.klass.register_name)
    line3 = '// Source: {}\n'.format(template.klass.header_file)
    line4 = '// ' + 93 * '=' + ' //\n'
    label = line1 + line2 + line3 + line4
    fout.write(label)

    # Get all the template parameters including nested class templates
    parameters = []
    t = template
    while t:
        parameters = t.parameters + parameters
        t = t.parent
    txt = 'template<' + ', '.join(parameters) + '>\n'
    fout.write(txt)

    # Template function
    args = 'py::module &mod, std::string const &name, bool const is_base=false'
    fout.write('void {}({}){{\n\n'.format(template.function_name, args))

    # Generate the class
    bind_class(template.klass, fout, config)

    # Nested class templates
    for ntemplate in template.nested_class_templates:
        bind_template(ntemplate, fout, config)


def bind_constructor(ctor, fout):
    """

    :param pybinder.wrap.ConstructorWrapper ctor:
    :param fout:
    :return:
    """
    if ctor.is_excluded:
        return

    params = ', '.join([p.register_name for p in ctor.parameters])

    args = ', '
    for p in ctor.parameters:
        dval = ''
        if p.default_value:
            dval = '={}'.format(p.default_value)
        args += 'py::arg(\"{}\")'.format(p.spelling) + dval + ', '

    fout.write('{}.def(py::init<{}>(){}R\"({})\");\n'.format(ctor.object_name,
                                                             params, args, ctor.docs))


def bind_method(klass, method, fout):
    """

    :param pybinder.wrap.ClassWrapper klass:
    :param pybinder.wrap.MethodWrapper method:
    :param fout:
    :return:
    """
    if method.is_excluded:
        return

    static = ''
    prefix = '{}::*'.format(klass.register_name)
    if method.is_static:
        static = '_static'
        prefix = '*'

    params = ', '.join([p.register_name for p in method.parameters])

    args = ', '
    for p in method.parameters:
        dval = ''
        if p.default_value:
            dval = '={}'.format(p.default_value)
        args += 'py::arg(\"{}\")'.format(p.spelling) + dval + ', '

    const = ''
    if method.is_const:
        const = ' const'

    fout.write(
        '{}.def{}(\"{}\", ({} ({})({}){}) &{}{}R\"({})\");\n'.format(method.object_name,
                                                                     static,
                                                                     method.python_name,
                                                                     method.result_name,
                                                                     prefix,
                                                                     params,
                                                                     const,
                                                                     method.register_name,
                                                                     args,
                                                                     method.docs))


def bind_class_iterator(klass, fout):
    """

    :param pybinder.wrap.ClassWrapper klass:
    :param fout:
    :return:
    """

    txt = '{}.def(\"__iter__\", [](const {}& self) {{return py::make_iterator(self.begin(), self.end());}}, {}());\n'.format(
        klass.object_name, klass.register_name, klass.keep_alive)
    fout.write(txt)
