import fnmatch
import os
import re

from clang.cindex import AccessSpecifier, CursorKind, Type, Cursor, c_uint, TypeKind
from cymbal import clangext

# Patches for libclang
clangext.monkeypatch_cursor('get_specialization',
                            'clang_getSpecializedCursorTemplate',
                            [Cursor], Cursor)

clangext.monkeypatch_cursor('get_template_kind',
                            'clang_getTemplateCursorKind',
                            [Cursor], c_uint)

clangext.monkeypatch_cursor('get_num_overloaded_decl',
                            'clang_getNumOverloadedDecls',
                            [Cursor], c_uint)

clangext.monkeypatch_cursor('get_overloaded_decl',
                            'clang_getOverloadedDecl',
                            [Cursor, c_uint], Cursor)

clangext.monkeypatch_type('get_arg_type',
                          'clang_getArgType',
                          [Type, c_uint], Type)


class CursorWrapper(object):
    """
    A cursor wrapper.

    :param clang.cindex.Cursor cursor: The clang cursor.
    """

    def __init__(self, cursor):
        self._cursor = cursor

        self.module_name = ''
        self.header_file = ''
        self.register_name = ''
        self.canonical_type_name = ''
        self.python_name = ''
        self.object_name = ''
        self.container = 'mod'

        self.is_excluded = False
        self.is_alias = False
        self.is_nested = False

        self.parent = None

        self.extra_includes = []

        self.before = []
        self.after = []

    def __eq__(self, other):
        return self.clang_cursor.hash == other.clang_cursor.hash

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.clang_cursor.hash

    def __repr__(self):
        return '{}: {}'.format(type(self).__name__, self.qualified_displayname)

    @property
    def referenced(self):
        return CursorWrapper(self.clang_cursor.referenced)

    @property
    def clang_cursor(self):
        """
        :return:
        :rtype: clang.cindex.Cursor
        """
        return self._cursor

    @property
    def is_null(self):
        return self.clang_cursor is None or self.clang_cursor.kind == CursorKind.NO_DECL_FOUND

    @property
    def type(self):
        return TypeWrapper(self.clang_cursor.type)

    @property
    def underlying_typedef_type(self):
        return TypeWrapper(self.clang_cursor.underlying_typedef_type)

    @property
    def displayname(self):
        return self.clang_cursor.displayname

    @property
    def spelling(self):
        return self.clang_cursor.spelling

    @property
    def token_spelling(self):
        return ' '.join([t.spelling for t in self.clang_cursor.get_tokens()])

    @property
    def source_file(self):
        file = self.clang_cursor.location.file
        if not file:
            return None
        return os.path.split(file.name)[-1]

    @property
    def docs(self):
        docs = self.clang_cursor.brief_comment
        if not docs:
            return docs
        return docs.replace('\"', '\'')

    @property
    def is_public(self):
        return self.clang_cursor.access_specifier == AccessSpecifier.PUBLIC

    @property
    def is_struct_decl(self):
        return self.clang_cursor.kind == CursorKind.STRUCT_DECL

    @property
    def is_enum_constant(self):
        return self.clang_cursor.kind == CursorKind.ENUM_CONSTANT_DECL

    @property
    def is_type_ref(self):
        return self.clang_cursor.kind == CursorKind.TYPE_REF

    @property
    def is_param_decl(self):
        return self.clang_cursor.kind == CursorKind.PARM_DECL

    @property
    def is_function_decl(self):
        return self.clang_cursor.kind == CursorKind.FUNCTION_DECL

    @property
    def is_enum_decl(self):
        return self.clang_cursor.kind == CursorKind.ENUM_DECL

    @property
    def is_private(self):
        return self.clang_cursor.access_specifier == AccessSpecifier.PRIVATE

    @property
    def is_protected(self):
        return self.clang_cursor.access_specifier == AccessSpecifier.PROTECTED

    @property
    def is_base_specifier(self):
        return self.clang_cursor.kind == CursorKind.CXX_BASE_SPECIFIER

    @property
    def is_typedef_decl(self):
        return self.clang_cursor.kind == CursorKind.TYPEDEF_DECL

    @property
    def is_destructor(self):
        return self.clang_cursor.kind == CursorKind.DESTRUCTOR

    @property
    def is_class_decl(self):
        return self.clang_cursor.kind == CursorKind.CLASS_DECL

    @property
    def is_class_template_decl(self):
        return self.clang_cursor.kind == CursorKind.CLASS_TEMPLATE

    @property
    def is_template_type_param(self):
        return self.clang_cursor.kind == CursorKind.TEMPLATE_TYPE_PARAMETER

    @property
    def is_template_non_type_param(self):
        return self.clang_cursor.kind == CursorKind.TEMPLATE_NON_TYPE_PARAMETER

    @property
    def is_template_template_param(self):
        return self.clang_cursor.kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER

    @property
    def is_template_ref(self):
        return self.clang_cursor.kind == CursorKind.TEMPLATE_REF

    @property
    def is_constructor(self):
        return self.clang_cursor.kind == CursorKind.CONSTRUCTOR

    @property
    def is_class_method(self):
        return self.clang_cursor.kind == CursorKind.CXX_METHOD

    @property
    def enum_value(self):
        return self.clang_cursor.enum_value

    @property
    def is_operator(self):
        return self.spelling.startswith('operator')

    @property
    def is_anonymous(self):
        return self.clang_cursor.is_anonymous()

    @property
    def result_type(self):
        return TypeWrapper(self.clang_cursor.result_type)

    def get_definition(self):
        if self.is_definition:
            return self
        return CursorWrapper(self.clang_cursor.get_definition())

    def get_children(self):
        for c in self.clang_cursor.get_children():
            yield CursorWrapper(c)

    def walk_preorder(self):
        for c in self.clang_cursor.walk_preorder():
            yield CursorWrapper(c)

    def get_method_parameters(self):
        params = []
        for p in self.get_children():
            if p.is_param_decl:
                params.append(p)
        return params

    def get_enum_constants(self):
        constants = []
        for c in self.get_children():
            if c.is_enum_constant:
                constants.append(c)
        return constants

    @property
    def is_definition(self):
        if self.is_null:
            return False
        return self.clang_cursor.is_definition()

    @property
    def has_public_destructor(self):
        for c in self.get_children():
            if c.is_destructor:
                return c.is_public
        return True

    @property
    def handle(self):
        # If this class is Standard_Transient
        if self.spelling == 'Standard_Transient':
            return 'opencascade::handle'

        # If this class has a private destructor
        if not self.has_public_destructor:
            return 'shared_ptr_nodelete'

        # If this class is derived from Standard_Transient
        for b in self.get_all_base_classes():
            if fnmatch.fnmatch(b.spelling, 'class Standard_Transient'):
                return 'opencascade::handle'

        # Use shared_ptr for everything else
        return 'shared_ptr'

    def get_specialization(self):
        """

        :return:
        """
        if self.is_class_template_decl:
            return self
        spec = self.clang_cursor.type.get_canonical().get_declaration().get_specialization()
        if spec and not spec.is_definition():
            spec = spec.get_definition()
        return CursorWrapper(spec)

    def get_base_classes(self):
        bases = []
        cursor = self

        # Special case for typedefs
        if self.is_typedef_decl:
            c = self.get_specialization()
            if c and not c.is_null:
                cursor = c

        for c in cursor.get_children():
            if c.is_base_specifier:
                bases.append(c)
        return bases

    def get_all_base_classes(self):
        bases = []

        def visit(c):
            for b in c.get_base_classes():
                bases.append(b)
                d = b.get_definition()
                if d and not d.is_null:
                    visit(d)

        visit(self)

        return bases

    def get_nested_classes(self):
        nested = []
        for c in self.get_children():
            if (c.is_class_decl or c.is_struct_decl) and c.is_definition:
                nested.append(c)
        return nested

    def get_template_params(self):
        params = []
        for c in self.get_children():
            if (c.is_template_type_param or c.is_template_non_type_param or
                    c.is_template_template_param):
                params.append(c)
        return params

    @property
    def semantic_parent(self):
        return CursorWrapper(self.clang_cursor.semantic_parent)

    @property
    def is_translation_unit(self):
        return self.clang_cursor.kind == CursorKind.TRANSLATION_UNIT

    @property
    def qualified_displayname(self):
        txt = [self.displayname]
        parent = self.semantic_parent
        while not parent.is_null and not parent.is_translation_unit:
            if parent.displayname:
                txt.insert(0, parent.displayname)
            parent = parent.semantic_parent
        name = '::'.join(txt)
        return name

    @property
    def qualified_spelling(self):
        txt = [self.spelling]
        parent = self.semantic_parent
        while not parent.is_translation_unit:
            if parent.spelling:
                txt.insert(0, parent.spelling)
            parent = parent.semantic_parent
        name = '::'.join(txt)
        return name

    @property
    def type_canonical_spelling(self):
        return self.clang_cursor.type.get_canonical().spelling

    def get_type_declaration(self):
        CursorWrapper(self.clang_cursor.type.get_declaration())

    @property
    def is_contained_in_class_template(self):
        if self.is_class_template_decl:
            return True
        parent = self.semantic_parent
        while not parent.is_translation_unit:
            if parent.is_class_template_decl:
                return True
            parent = parent.semantic_parent
        return False

    def get_trampolines(self):
        """

        :return:
        """
        return []


class TypeWrapper(object):
    """
    A type.

    :param clang.cindex.Type type_: The clang type cursor.
    """

    def __init__(self, type_):
        name = type_.spelling
        if not isinstance(type_, Type):
            raise RuntimeError('The type_ is not a clang.cindex.Type object: {}'.format(name))

        self._type = type_

    def __repr__(self):
        return 'Type: {} ({})'.format(self.spelling, self._type.kind)

    @property
    def spelling(self):
        return self._type.spelling

    @property
    def canonical_spelling(self):
        return self._type.get_canonical().spelling

    @property
    def num_template_parameters(self):
        return self._type.get_num_template_arguments()

    @property
    def is_invalid(self):
        return self._type.kind == TypeKind.INVALID

    @property
    def is_bool(self):
        return self._type.kind == TypeKind.BOOL

    @property
    def is_char(self):
        return self._type.kind == TypeKind.CHAR_S

    @property
    def is_int(self):
        kind = self._type.kind
        return kind == TypeKind.INT or kind == TypeKind.UINT

    @property
    def is_long_long(self):
        return self._type.kind == TypeKind.LONGLONG

    @property
    def is_pointer(self):
        return self._type.kind == TypeKind.POINTER

    @property
    def is_lvalue(self):
        return self._type.kind == TypeKind.LVALUEREFERENCE

    @property
    def is_rvalue(self):
        return self._type.kind == TypeKind.RVALUEREFERENCE

    @property
    def is_pointer_like(self):
        return self.is_pointer or self.is_lvalue or self.is_rvalue

    @property
    def is_elaborated(self):
        return self._type.kind == TypeKind.ELABORATED

    @property
    def is_unexposed(self):
        return self._type.kind == TypeKind.UNEXPOSED

    @property
    def is_record(self):
        return self._type.kind == TypeKind.RECORD

    @property
    def is_typedef(self):
        return self._type.kind == TypeKind.TYPEDEF

    @property
    def is_enum(self):
        return self._type.kind == TypeKind.ENUM

    @property
    def is_void(self):
        return self._type.kind == TypeKind.VOID

    @property
    def is_array_like(self):
        return (self.is_constant_array or self.is_incomplete_array or self.is_variable_array or
                self.is_dependent_sized_array)

    @property
    def is_constant_array(self):
        return self._type.kind == TypeKind.CONSTANTARRAY

    @property
    def is_vector(self):
        return self._type.kind == TypeKind.VECTOR

    @property
    def is_incomplete_array(self):
        return self._type.kind == TypeKind.INCOMPLETEARRAY

    @property
    def is_variable_array(self):
        return self._type.kind == TypeKind.VARIABLEARRAY

    @property
    def is_dependent_sized_array(self):
        return self._type.kind == TypeKind.DEPENDENTSIZEDARRAY

    @property
    def is_const_qualified(self):
        return self._type.is_const_qualified()

    def get_declaration(self):
        return CursorWrapper(self._type.get_declaration())

    def get_canonical(self):
        return TypeWrapper(self._type.get_canonical())

    def get_pointee(self):
        return TypeWrapper(self._type.get_pointee())

    def get_named_type(self):
        return TypeWrapper(self._type.get_named_type())

    def get_template_parameter_type(self, indx):
        """

        :param int indx:
        :return:
        """
        return TypeWrapper(self._type.get_template_argument_type(indx))

    def get_argument_type(self, indx):
        """

        :param indx:
        :return:
        """
        return TypeWrapper(self._type.get_arg_type(indx))

    def get_result(self):
        """

        :return:
        """
        return TypeWrapper(self._type.get_result())


class ClassWrapper(CursorWrapper):
    """
    Class (and struct) wrapper.

    :param pybinder.wrap.CursorWrapper cursor:

    """

    def __init__(self, cursor):
        super(ClassWrapper, self).__init__(cursor.clang_cursor)

        self.has_hidden_destructor = False
        self.holder_type = ''

        self.bases = []
        self.extra_bases = []
        self.trampoline = None

        self.is_template = False
        self.nested_classes = []
        self.nested_class_templates = []
        self.parameters = []

        self.nested_enums = []

        self.constructors = []
        self.methods = []
        self.fields = []

        self.is_iterator = False
        self.keep_alive = 'py::keep_alive<0, 1>'

    @property
    def is_abstract(self):
        return self.clang_cursor.is_abstract_record()

    def is_derived_from(self, name):
        """

        :param name:
        :return:
        """
        out = [False]

        def visit(c):
            for b in c.bases:
                if b.base_name == name:
                    out[0] = True
                visit(b)

        visit(self)
        return out[0]

    def get_all_bases(self):
        """

        :return:
        """
        bases = []

        def visit(c):
            for b in c.bases:
                bases.append(b)
                visit(b)

        visit(self)
        return bases

    def get_trampolines(self):
        """
        Get all trampoline classes for this class.

        :return:
        """
        tclasses = []

        def get_tclasses(klass):
            if klass.trampoline:
                tclasses.append(klass.trampoline)
            for nklass in klass.nested_classes:
                get_tclasses(nklass)
            for ntemplate in klass.nested_class_templates:
                get_tclasses(ntemplate.klass)

        get_tclasses(self)

        return tclasses


class BaseClassWrapper(CursorWrapper):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(BaseClassWrapper, self).__init__(cursor.clang_cursor)

        # Exclude by default and require them to be found during processing. This seems to be more
        # robust than having them included by default and having to exclude them.
        self.is_excluded = True

        self.base_name = ''
        self.bases = []

        self.is_class = False
        self.superclass = None
        self.referenced_name = ''

        self.is_template = False
        self.is_templated = False
        self.template = None
        self.parameters = ''
        self.referenced_template = ''

        self.is_typedef = False
        self.is_template_param_base = False

    def __repr__(self):
        return '{}: {}'.format(type(self).__name__, self.referenced.qualified_displayname)


class ConstructorWrapper(CursorWrapper):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(ConstructorWrapper, self).__init__(cursor.clang_cursor)

        self.parameters = []

    @property
    def is_converting_constructor(self):
        return self.clang_cursor.is_converting_constructor()

    @property
    def is_copy_constructor(self):
        return self.clang_cursor.is_copy_constructor()

    @property
    def is_default_constructor(self):
        return self.clang_cursor.is_default_constructor()

    @property
    def is_move_constructor(self):
        return self.clang_cursor.is_move_constructor()


class EnumWrapper(CursorWrapper):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(EnumWrapper, self).__init__(cursor.clang_cursor)

        self.constants = []


class EnumConstantWrapper(CursorWrapper):
    """
    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(EnumConstantWrapper, self).__init__(cursor.clang_cursor)


class FunctionWrapper(CursorWrapper):
    """
    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(FunctionWrapper, self).__init__(cursor.clang_cursor)

        self.result_name = ''
        self.parameters = []


class MethodWrapper(CursorWrapper):
    """
    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(MethodWrapper, self).__init__(cursor.clang_cursor)

        self.result_name = ''
        self.parameters = []

    @property
    def is_static(self):
        return self.clang_cursor.is_static_method()

    @property
    def is_const(self):
        return self.clang_cursor.is_const_method()

    @property
    def is_virtual(self):
        return self.clang_cursor.is_virtual_method()

    @property
    def is_pure_virtual(self):
        return self.clang_cursor.is_pure_virtual_method()


class ParameterWrapper(CursorWrapper):
    """
    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(ParameterWrapper, self).__init__(cursor.clang_cursor)

        self.default_value = ''

    def get_default_value(self):
        txt = self.token_spelling
        if '=' in txt:
            return txt.split('=', 1)[-1].strip()
        return ''


class ClassTemplateWrapper(CursorWrapper):
    """
    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(ClassTemplateWrapper, self).__init__(cursor.clang_cursor)

        self.function_name = ''
        self.source_name = ''

        self.klass = None
        self.parameters = []

        self.nested_class_templates = []

    def get_trampolines(self):
        """

        :return:
        """
        return self.klass.get_trampolines()


class TypedefWrapper(CursorWrapper):
    """
    :param pybinder.wrap.CursorWrapper cursor:
    """

    def __init__(self, cursor):
        super(TypedefWrapper, self).__init__(cursor.clang_cursor)

        self.bases = []
        self.extra_bases = []

        self.function_name = ''

        self.is_templated = False
        self.underlying_template_name = ''
        self.parameters = ''

        self.alias = None

    def get_all_bases(self):
        """

        :return:
        """
        bases = []

        def visit(c):
            for b in c.bases:
                bases.append(b)
                visit(b)

        visit(self)
        return bases


class TrampolineClassWrapper(object):
    """
    :param pybinder.wrap.ClassWrapper klass:
    """

    def __init__(self, klass):
        self.is_excluded = True
        self.class_name = ''
        self.base_name = ''
        self.template_name = ''
        self.klass = klass
        self.parameters = []
        self.pure_virtual_methods = []


def wrap_enum_cursor(cursor):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :return:
    """
    # Initialize
    enum = EnumWrapper(cursor)

    # Set header file
    enum.header_file = os.path.split(enum.clang_cursor.location.file.name)[-1]

    # Set names
    enum.register_name = cursor.type.spelling
    enum.python_name = cursor.type.spelling

    # Process enum constants
    for c in cursor.get_children():
        if not c.is_enum_constant:
            continue

        ec = EnumConstantWrapper(c)
        ec.register_name = c.qualified_spelling
        ec.python_name = c.spelling
        enum.constants.append(ec)

    return enum


def wrap_function_cursor(cursor):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :return:
    """
    # Initialize
    func = FunctionWrapper(cursor)

    # Set header file
    func.header_file = os.path.split(func.clang_cursor.location.file.name)[-1]

    # Set names
    func.register_name = cursor.spelling
    func.python_name = cursor.spelling
    func.result_name = cursor.result_type.spelling

    # Exclude if an operator
    if func.register_name.startswith('operator'):
        func.is_excluded = True

    # Process parameters
    for c in cursor.get_children():
        if not c.is_param_decl:
            continue

        p = wrap_method_parameter(c)
        func.parameters.append(p)

    return func


def wrap_method_parameter(cursor):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :return:
    """
    # Initialize
    param = ParameterWrapper(cursor)

    # Set names
    param.register_name = get_type_spelling(cursor.type)
    param.python_name = cursor.spelling

    # Default value
    param.default_value = param.get_default_value()

    return param


def wrap_class_cursor(cursor, config, is_class_template=False):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :param pybinder.configure.Configurator config:
    :param bool is_class_template:
    :return:
    """
    # Initialize
    klass = ClassWrapper(cursor)

    # Set header file
    klass.header_file = os.path.split(klass.clang_cursor.location.file.name)[-1]

    # Set names
    if is_class_template:
        klass.is_template = True
        klass.register_name = cursor.qualified_displayname
        klass.python_name = sanitize_name(cursor.qualified_spelling)
        klass.object_name = 'cls_' + klass.python_name
    else:
        klass.register_name = cursor.type.spelling
        klass.python_name = sanitize_name(cursor.type.spelling)
        klass.object_name = 'cls_' + klass.python_name
        klass.canonical_type_name = cursor.type.canonical_spelling

    # Process children
    for c in klass.get_children():
        # Check for a hidden destructor
        if c.is_destructor and not c.is_public:
            klass.has_hidden_destructor = True

        # Methods
        if c.is_class_method:
            m = wrap_method_cursor(c, config)
            m.object_name = klass.object_name
            klass.methods.append(m)

        # Public only beyond this
        if not c.is_public:
            continue

        # Bases
        if c.is_base_specifier:
            klass.bases.append(wrap_base_cursor(c))

        # Constructors
        if c.is_constructor:
            ctor = wrap_constructor(c, config)
            ctor.object_name = klass.object_name
            klass.constructors.append(ctor)

        # TODO Fields

        # Nested enums
        if c.is_enum_decl:
            enum = wrap_enum_cursor(c)
            enum.is_nested = True
            enum.parent = klass
            enum.container = klass.object_name
            enum.python_name = c.spelling
            klass.nested_enums.append(enum)

        # Nested classes
        if (c.is_class_decl or c.is_struct_decl) and c.is_definition:
            nklass = wrap_class_cursor(c, config, is_class_template)
            nklass.is_nested = True
            nklass.parent = klass
            nklass.container = klass.object_name
            nklass.python_name = c.spelling
            klass.nested_classes.append(nklass)

        # Nested class templates
        if c.is_class_template_decl and not is_class_template:
            ntemplate = wrap_class_template_cursor(c, config)
            ntemplate.is_nested = True
            ntemplate.parent = klass
            ntemplate.python_name = sanitize_name(ntemplate.qualified_spelling)
            ntemplate.function_name = 'bind_' + ntemplate.python_name
            ntemplate.source_name = ntemplate.function_name + '.hxx'
            klass.nested_class_templates.append(ntemplate)

    # Wrap trampoline class
    if klass.is_abstract:
        klass.trampoline = wrap_trampoline_class(klass, is_class_template)

    # Set holder type
    if klass.has_hidden_destructor:
        klass.holder_type = 'shared_ptr_nodelete'
    else:
        klass.holder_type = 'shared_ptr'

    # Check if (likely) an iterator
    method_names = {m.spelling for m in klass.methods}
    iterator_names = {'begin', 'end', 'cbegin', 'cend'}
    if iterator_names.issubset(method_names):
        klass.is_iterator = True

    return klass


def wrap_trampoline_class(klass, is_class_template=False):
    """

    :param pybinder.wrap.ClassWrapper klass:
    :param bool is_class_template:
    :return:
    """
    # Initialize
    trampoline = TrampolineClassWrapper(klass)

    # Get template parameters
    if klass.is_contained_in_class_template:
        trampoline.parameters = get_template_parameters_token_spelling(klass.semantic_parent)
    else:
        trampoline.parameters = get_template_parameters_token_spelling(klass)

    # Set names
    if is_class_template:
        trampoline.class_name = 'Py' + sanitize_name(klass.qualified_spelling)
        if klass.is_contained_in_class_template:
            params = parse_template_parameters(klass.semantic_parent.qualified_displayname)
        else:
            params = parse_template_parameters(klass.qualified_displayname)
        trampoline.base_name = trampoline.class_name + params
    else:
        trampoline.class_name = 'Py' + sanitize_name(klass.register_name)
        trampoline.base_name = trampoline.class_name

    # Get pure virtual methods
    for method in klass.methods:
        if method.is_pure_virtual:
            trampoline.pure_virtual_methods.append(method)

    return trampoline


def wrap_base_cursor(cursor):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :return:
    """

    # Initialize
    base = BaseClassWrapper(cursor)

    # Set name
    base.referenced_name = cursor.referenced.qualified_displayname

    # Handle template parameters as bases
    if not base.referenced_name and base.referenced.is_null:
        base.referenced_name = cursor.type.spelling
        base.base_name = base.referenced_name
        base.is_template_param_base = True
        return base

    # Use the reference to determine the base type
    ref = cursor.referenced
    if ref.is_class_decl or ref.is_struct_decl:
        base.is_class = True
    elif ref.is_typedef_decl:
        base.is_typedef = True
    elif ref.is_class_template_decl:
        base.is_template = True
    else:
        msg = 'Unknown base type encountered {}'.format(base)
        raise RuntimeError(msg)

    # Get bases
    template = ref.get_specialization()
    if not template.is_null:
        base.is_templated = True
        base.referenced_template = template.qualified_displayname
        for c in template.get_children():
            if c.is_base_specifier and c.is_public:
                base.bases.append(wrap_base_cursor(c))
    else:
        # Use the reference to retrieve additional bases
        for c in ref.get_children():
            if c.is_base_specifier and c.is_public:
                base.bases.append(wrap_base_cursor(c))

    # Get base name
    if base.is_template:
        base.base_name = base.type.spelling
    else:
        base.base_name = ref.type.spelling

    # Get parameters
    if '<' in base.base_name:
        base.parameters = parse_template_parameters(base.base_name)

    return base


def wrap_class_template_cursor(cursor, config):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :param pybinder.configure.Configurator config:
    :return:
    """
    # Initialize
    template = ClassTemplateWrapper(cursor)

    # Set header file
    template.header_file = os.path.split(template.clang_cursor.location.file.name)[-1]

    # Get template parameters
    template.parameters = get_template_parameters_token_spelling(cursor)

    # Set names
    template.register_name = cursor.qualified_displayname
    template.function_name = 'bind_' + cursor.spelling
    template.source_name = template.function_name + '.hxx'

    # Wrap the class
    template.klass = wrap_class_cursor(cursor, config, True)

    # Wrap nested class templates
    for c in template.get_children():
        if not c.is_public:
            continue

        if (c.is_class_template_decl or c.is_class_decl or c.is_struct_decl) and c.is_definition:
            ntemplate = wrap_class_template_cursor(c, config)
            ntemplate.is_nested = True
            ntemplate.parent = template
            ntemplate.register_name = ntemplate.klass.register_name
            ntemplate.function_name = 'bind_' + ntemplate.klass.python_name
            ntemplate.source_name = template.source_name
            template.nested_class_templates.append(ntemplate)

    return template


def wrap_typedef_cursor(cursor):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :return:
    """
    # Initialize
    typedef = TypedefWrapper(cursor)

    # Set header file
    typedef.header_file = os.path.split(typedef.clang_cursor.location.file.name)[-1]

    # Set names
    typedef.register_name = cursor.type.spelling
    typedef.python_name = cursor.type.spelling
    typedef.canonical_type_name = cursor.underlying_typedef_type.canonical_spelling

    # Use the underlying class or template to search for base classes
    underlying_type = cursor.underlying_typedef_type.get_canonical()
    underlying_cursor = underlying_type.get_declaration()
    underlying_template = underlying_cursor.get_specialization()
    if not underlying_template.is_null:
        typedef.is_templated = True
        typedef.underlying_template_name = underlying_template.qualified_displayname
        typedef.parameters = parse_template_parameters(underlying_type.spelling)
        base_cursor = underlying_template
    elif underlying_cursor.is_class_decl or underlying_cursor.is_struct_decl:
        base_cursor = underlying_cursor
    else:
        # Built-in type?
        base_cursor = typedef

    # Get bases
    for c in base_cursor.get_children():
        if c.is_base_specifier:
            typedef.bases.append(wrap_base_cursor(c))

    return typedef


def sanitize_name(name):
    """

    :param str name:
    :return:
    """
    # Sanitize the name to make it suitable for Python
    name = name.replace('::', '_')
    name = name.replace('<', '_')
    name = name.replace('>', '_')
    name = name.strip('_')
    return name


def wrap_constructor(cursor, config):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :param pybinder.configure.Configurator config:
    :return:
    """
    # Initialize
    ctor = ConstructorWrapper(cursor)

    # Exclude move and converting constructors
    if ctor.is_move_constructor or ctor.is_converting_constructor:
        ctor.is_excluded = True

    # Set names
    ctor.register_name = cursor.qualified_displayname

    # Check if excluded
    if config.is_excluded_constructor(ctor.semantic_parent.qualified_displayname,
                                      ctor.register_name):
        ctor.is_excluded = True

    # Process parameters
    for c in cursor.get_children():
        if not c.is_param_decl:
            continue

        p = wrap_method_parameter(c)
        ctor.parameters.append(p)

        # Check for unsupported parameter
        if not is_supported_parameter(p):
            ctor.is_excluded = True

    return ctor


def wrap_method_cursor(cursor, config):
    """

    :param pybinder.wrap.CursorWrapper cursor:
    :param pybinder.configure.Configurator config:
    :return:
    """
    # Initialize
    method = MethodWrapper(cursor)

    # Exclude if not public (but we might need for trampoline class)
    if not method.is_public:
        method.is_excluded = True

    # Set names
    method.register_name = '{}::{}'.format(cursor.semantic_parent.qualified_displayname,
                                           cursor.spelling)

    # Append "_s" for static methods
    if method.is_static:
        method.python_name = cursor.spelling + '_s'
    else:
        method.python_name = cursor.spelling

    # Result name
    method.result_name = get_type_spelling(cursor.result_type)

    # Process parameters
    for c in cursor.get_children():
        if not c.is_param_decl:
            continue

        p = wrap_method_parameter(c)
        method.parameters.append(p)

        # Check for unsupported parameters
        if not is_supported_parameter(p):
            method.is_excluded = True

    # Check excluded
    if config.is_excluded_method(method.semantic_parent.qualified_displayname,
                                 method.python_name):
        method.is_excluded = True

    return method


def sanitize_template_parameter(qname, spelling, txt):
    """

    :param str qname:
    :param str spelling:
    :param str txt:
    :return:
    """
    return txt.replace(spelling, qname)


def get_type_spelling(ptype):
    """

    :param pybinder.wrap.TypeWrapper ptype:
    :return:
    """
    # The logic below is one of the less robust parts of the entire process. It was mostly derived
    # by trial and error on edge cases rather than knowing exactly what the right thing to do is.
    # The easiest (and preferred) way to do it would simply be "return ptype.spelling" but that
    # seems to sometimes miss pieces of the type definition. This seems to mostly be a problem
    # with things defined in a class (e.g., nested class) where the class itself doesn't need a
    # fully qualified definition but the bindings do. A simple example is in a class template where
    # the source code may be "Template::Foo" which is fine for the template itself, but clang picks
    # up that and "ptype.spelling" returns "Template::Foo" rather than "Template<T>::Foo" which
    # is what the binding source needs. In this example the fully qualified displayname picks up the
    # the template parameters (as used below).

    # In summary, the approach below in its current form is mostly just hoping that it works and is
    # likely not suitable as a "catch all" process. Note that a type "record" in this case seems to
    # represent a class/struct in clang.

    # Get the pointer qualifier
    if ptype.is_lvalue:
        ptr = '&'
    elif ptype.is_rvalue:
        ptr = '&&'
    elif ptype.is_pointer:
        ptr = '*'
    else:
        ptr = ''

    # Get the pointee
    if ptype.is_pointer_like:
        pointee = ptype.get_pointee()
    else:
        pointee = ptype

    # Check for const qualified
    if pointee.is_const_qualified:
        const = 'const '
    else:
        const = ''

    # To start, keep iterating and retrieving the elaborated type until it is not longer elaborated.
    # If it's a record, typedef, or enum return the type spelling.
    while pointee.is_elaborated:
        pointee = pointee.get_named_type()
        if pointee.is_record or pointee.is_typedef or pointee.is_enum:
            return ptype.spelling

    # Get the definition of the type
    decl = pointee.get_declaration()
    if not decl.is_definition:
        # It can be the case that a declaration is not a definition but a valid class, struct,
        # typedef, or enum. In this case, use the qualified displayname.
        if decl.is_class_decl or decl.is_struct_decl or decl.is_enum_decl or decl.is_typedef_decl:
            return const + decl.qualified_displayname + ptr
        else:
            # If it's not a definition and none of the above, it is likely something like a template
            # parameter. In this case, just return the type spelling and hope for the best.
            return ptype.spelling

    # At this point you should have a definition. Now, if the pointee is a record, typedef, or enum
    # you should be able to use the qualified displayname.
    if pointee.is_record or pointee.is_typedef or pointee.is_enum:
        return const + decl.qualified_displayname + ptr

    # Deal with template definitions in a special way to better handle edge cases for template
    # parameters. The challenge here is that in source things may be defined like
    # "Template<Bar>" when what you really need in the bindings is "Template<Foo::Bar>" or
    # "Template<Foo<T>::Bar>" in the case of a template. Start by attempting to retrieve the
    # template specialization and taking our best guess at what to do next...
    template = decl.get_specialization()
    if template.is_null:
        # This is sometimes encountered in the case of class templates where the return type of
        # a method might be "Template<T>" as one example. In general it seems the things that fall
        # here are a definition (since we checked for that above) but not a record, typedef, or
        # enum. They usually (but not always) are of type kind "unexposed" if that provides any
        # hints to make this more robust in the future.
        return const + decl.type.spelling + ptr
    elif template.is_class_template_decl:
        # If the template is in fact a class template, iterate through the template parameters and
        # try to make a best guess at what the right type spelling should be.
        params = []
        for i in range(pointee.num_template_parameters):
            p = pointee.get_template_parameter_type(i)

            # If the type is invalid just return the pointee retrieved earlier. This seems to happen
            # most frequently for the second template parameter of a class template for some reason.
            # That is, if you have "Template<A, B>" clang will return the spelling of the first
            # parameter as "A" but then the second parameter is (seemingly) always invalid.
            # Returning the original pointee seems to be a best guess at what to do but if it works
            # it seems more by accident that anything else...
            if p.is_invalid:
                return pointee.spelling + ptr

            # Get the definition of the template parameter type
            decl = p.get_declaration()
            if decl.is_class_template_decl:
                # If the type is a template itself, use the spelling of the template parameter type
                # rather than the template qualified displayname. Using the qualified displayname of
                # the template would result in "Template<A, B>" (i.e., the class template itself)
                # rather than "Template<Foo, Bar>" as defined in the type itself.
                name = p.spelling
            elif decl.is_definition:
                # If the declaration is a definition, use the qualified displayname. This helps
                # catch cases where it's defined as "Template<Bar>" in the source but the bindings
                # need "Template<Foo::Bar>" to compile.
                name = decl.qualified_displayname
            else:
                # If nothing else, just use the parameter type spelling mostly as a fallback.
                name = p.spelling

            # Make sure some parameter name was determined. If not it will be blank and the bindings
            # would fail to compile.
            if not name:
                msg = 'Unhandled template parameter type spelling: {}'.format(ptype)
                raise RuntimeError(msg)

            # Add the name to the template parameter list
            params.append(name)

        # Put it all together and return
        t = template.qualified_spelling + '<' + ', '.join(params) + '>'
        return const + t + ptr
    else:
        # Leave this here in case an edge case is encountered and more work is needed
        msg = 'Unhandled type spelling: {}'.format(ptype)
        raise RuntimeError(msg)


def get_template_parameters_token_spelling(cursor):
    """

    :param cursor:
    :return:
    """
    parameters = []
    for c in cursor.get_children():
        if c.is_template_type_param or c.is_template_non_type_param or c.is_template_template_param:
            parameters.append(c.token_spelling)
    return parameters


def get_template_parameters_spelling(cursor):
    """

    :param cursor:
    :return:
    """
    parameters = []
    for c in cursor.get_children():
        if c.is_template_type_param or c.is_template_non_type_param or c.is_template_template_param:
            parameters.append(c.spelling)
    return parameters


def parse_template_parameters(name):
    """

    :param name:
    :return:
    """
    return '<' + re.search("<(.*)>", name).group(1) + '>'


def is_supported_parameter(param):
    """

    :param pybinder.wrap.ParameterWrapper param:
    :return:
    """
    if param.type.is_pointer_like:
        pointee = param.type.get_pointee()
    else:
        pointee = param.type

    # Pointer to pointer
    if pointee.is_pointer_like:
        return False

    # Arrays
    if pointee.is_array_like:
        return False

    return True
