import os

from pybinder.configure import Configurator
from pybinder.generate import generate_bindings
from pybinder.parse import Parser
from pybinder.utilities import find_include_path


def run():
    # Generate configuration from file
    config = Configurator.from_toml('occt_clang.toml')

    # Get the root directory of the conda environment
    conda_prefix = os.environ.get('CONDA_PREFIX')

    # Find include paths
    clang_include_path = find_include_path('__stddef_max_align_t.h', conda_prefix)
    occt_include_path = find_include_path('Standard.hxx', conda_prefix)
    vtk_include_path = find_include_path('vtk_doubleconversion.h', conda_prefix)
    rapidjson_include_path = find_include_path('rapidjson.h', conda_prefix)
    rapidjson_include_path = os.path.split(rapidjson_include_path)[0]

    print('Include directories:')
    print('\tClang: {}'.format(clang_include_path))
    print('\tOpenCASCADE: {}'.format(occt_include_path))
    print('\tVTK: {}'.format(vtk_include_path))
    print('\tRapidjson: {}'.format(rapidjson_include_path))

    config.add_include_paths(clang_include_path, occt_include_path, vtk_include_path,
                             rapidjson_include_path)

    # Parse
    print('Parsing headers...')
    parser = Parser(config)
    parser.generate_header_file(occt_include_path)
    parser.parse()
    parser.dump_diagnostics(0)

    # Generate
    print('Generating bindings...')
    generate_bindings(parser, config, './src', True)


if __name__ == '__main__':
    run()
