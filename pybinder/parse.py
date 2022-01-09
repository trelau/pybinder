import os

from clang.cindex import Index, TranslationUnit

from pybinder.wrap import CursorWrapper


class Parser(object):
    """
    Parser

    :param pybinder.configure.Configurator config:
    """

    def __init__(self, config):
        self._config = config
        self._tu = None

    @property
    def config(self):
        """
        :return:
        :rtype: pybinder.configure.Configurator
        """
        return self._config

    def generate_header_file(self, path):
        """

        :param path:
        :return:
        """
        if self.config.debug_mode:
            include_file = self.config.debug_header_file
            potential_includes = self.config.debug_headers
        else:
            include_file = self.config.header_file
            potential_includes = os.listdir(path)

        potential_includes.sort(key=str.lower)

        fout = open(include_file, 'w')
        if self.config.platform == 'win32':
            fout.write('#include <windows.h>\n')
        for h in potential_includes:
            if self.config.is_excluded_header(h):
                continue
            fout.write('#include <{}>\n'.format(h))
            self.config.available_includes.add(h)

        fout.close()

    def parse(self):
        """
        Parse the header files.

        :return:
        """
        if self.config.debug_mode:
            header_file = self.config.debug_header_file
        else:
            header_file = self.config.header_file

        indx = Index.create()
        args = list(self.config.args)
        for p in self.config.include_paths:
            args.append('-I{}'.format(p))
        tu = indx.parse(header_file, args, options=TranslationUnit.PARSE_INCOMPLETE)
        self._tu = tu

    def save(self, filename):
        """

        :param filename:
        :return:
        """
        self._tu.save(filename)

    def load(self, filename):
        """

        :param filename:
        :return:
        """
        indx = Index.create()
        self._tu = TranslationUnit.from_ast_file(filename, indx)

    def dump_diagnostics(self, severity=4):
        """

        :param severity:
        :return:
        """
        print('----------------------')
        print('DIAGNOSTIC INFORMATION')
        print('----------------------')
        other_issues = 0
        for diag in self._tu.diagnostics:
            if diag.severity < severity:
                other_issues += 1
                continue
            print('---')
            print('SEVERITY: {}'.format(diag.severity))
            print('LOCATION: {}'.format(diag.location))
            print('MESSAGE: {}'.format(diag.spelling))
            print('---')

        msg = 'Complete with {} issues with lower than {} severity not shown.'.format(other_issues,
                                                                                      severity)
        print(msg)
        print('----------------------')

    def get_children(self):
        """
        Get all children cursors from the main translation unit.

        :return:
        """
        for c in self._tu.cursor.get_children():
            yield CursorWrapper(c)

    def walk_preorder(self):
        """
        Get all children cursors from the main translation unit.

        :return:
        """
        for c in self._tu.cursor.walk_preorder():
            yield CursorWrapper(c)
