import fnmatch
import os
import sys
import warnings

import toml


class Configurator(object):
    """
    Configurations options and data.
    """

    def __init__(self):
        self.platform = sys.platform

        # Source file preamble
        self.preamble = ''

        # Debug
        self.debug_mode = False
        self.debug_header_file = ''
        self.debug_headers = []

        # Parse
        self.args = []
        self.header_extensions = []
        self.header_file = ''
        self.include_paths = []
        self.excluded_headers = []

        # Bind
        self.common_headers = []

        # Exclude
        self.excluded_classes = []
        self.excluded_typedefs = []
        self.excluded_methods = []
        self.excluded_modules = {}

        # Module data
        self.modules = {}

        # Class data
        self.classes = {}

        # Generated during parsing
        self.available_includes = set()
        self.available_templates = set()

    @staticmethod
    def from_toml(fn):
        """
        Create a configuration from a toml file.

        :param str fn:

        :return:
        :rtype: pybinder.configure.Configurator
        """
        data = toml.load(fn)
        config = Configurator()

        # Preamble
        config.preamble = data['preamble']

        # Debug
        config.debug_mode = data['Debug']['debug_mode'].lower() == 'true'
        config.debug_header_file = data['Debug']['header_file']
        config.debug_headers = data['Debug']['headers']

        # Parse
        config.args = data['Parse']['args']
        config.header_extensions = data['Parse']['header_extensions']
        config.header_file = data['Parse']['header_file']
        config.excluded_headers = data['Parse']['excluded_headers']

        # Bind
        config.common_headers = data['Bind']['common_headers']

        # Exclude
        config.excluded_classes = data['Exclude']['classes']
        config.excluded_typedefs = data['Exclude']['typedefs']
        config.excluded_methods = data['Exclude']['methods']
        config.excluded_modules = data['Exclude']['Modules']

        # Module data
        config.modules = data['Modules']

        # Class data
        config.classes = data['Classes']

        return config

    def add_include_paths(self, *args):
        """
        Add include paths for parsing headers.

        :param args:

        :return:
        """
        for p in args:
            if os.path.exists(p):
                self.include_paths.append(p)
            else:
                msg = 'Non-existent include path cannot be added: {}'.format(p)
                warnings.warn(msg)

    def is_excluded_header(self, h):
        """

        :param str h:
        :return:
        """
        if h in self.excluded_headers:
            return True
        for ext in self.header_extensions:
            if h.endswith(ext):
                return False
        return True

    def is_excluded_module(self, mod):
        """

        :param str mod:
        :return:
        """
        # Platform specific modules to exclude
        if mod in self.excluded_modules[self.platform]:
            return True

        # Any module to exclude
        if mod in self.excluded_modules['any']:
            return True

        return False

    def is_available_header(self, h):
        """

        :param str h:
        :return:
        """
        return h in self.available_includes

    def is_excluded_function(self, mod, func):
        """

        :param str mod:
        :param str func:

        :return:
        """
        try:
            return func in self.modules[mod]['excluded_functions']
        except KeyError:
            return False

    def is_excluded_class(self, mod, klass):
        """

        :param str mod:
        :param str klass:
        :return:
        """
        # Global check
        for pattern in self.excluded_classes:
            if fnmatch.fnmatch(klass, pattern):
                return True

        # Module check
        try:
            return klass in self.modules[mod]['excluded_classes']
        except KeyError:
            return False

    def is_excluded_method(self, klass, method):
        """

        :param klass:
        :param method:
        :return:
        """
        # Global check
        for pattern in self.excluded_methods:
            if fnmatch.fnmatch(method, pattern):
                return True

        # Class check
        try:
            return method in self.classes[klass]['excluded_methods']
        except KeyError:
            return False

    def is_excluded_constructor(self, klass, ctor):
        """

        :param str klass:
        :param str ctor:
        :return:
        """
        try:
            return ctor in self.classes[klass]['excluded_constructors']
        except KeyError:
            return False

    def is_excluded_typedef(self, mod, typedef):
        """

        :param str mod:
        :param str typedef:

        :return:
        """
        # Global check
        for pattern in self.excluded_typedefs:
            if fnmatch.fnmatch(typedef, pattern):
                return True

        # Module check
        try:
            return typedef in self.modules[mod]['excluded_typedefs']
        except KeyError:
            return False

    def is_available_template(self, t):
        """

        :param str t:
        :return:
        """
        return t in self.available_templates

    def get_extra_headers(self, mod):
        """

        :param mod:
        :return:
        """
        try:
            return self.modules[mod]['extra_headers']
        except KeyError:
            return []

    def get_class_before(self, klass):
        """

        :param str klass:

        :return:
        :rtype: list(str)
        """
        try:
            return self.classes[klass]['before']
        except KeyError:
            return []

    def get_class_after(self, klass):
        """

        :param str klass:

        :return:
        :rtype: list(str)
        """
        try:
            return self.classes[klass]['after']
        except KeyError:
            return []
