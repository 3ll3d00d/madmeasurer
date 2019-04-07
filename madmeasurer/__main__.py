import argparse
import logging
import os
import sys
from madmeasurer.loggers import main_logger, csv_logger, output_handler
from madmeasurer import search_path


class EnvDefault(argparse.Action):
    '''
    allows an arg to use an env var as a default value.
    '''

    def __init__(self, envvar, required=True, default=None, **kwargs):
        if not default and envvar:
            if envvar in os.environ:
                default = os.environ[envvar]
        if required and default:
            required = False
        super(EnvDefault, self).__init__(default=default, required=required, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, values)


def main():
    arg_parser = argparse.ArgumentParser(description='madmeasurer for BDMV')
    arg_parser.add_argument('paths', default=[os.getcwd()], nargs='+',
                            help='Search paths')

    group = arg_parser.add_argument_group('Search')
    group.add_argument('-d', '--depth', type=int, default=-1,
                       help='''
    Maximum folder search depth
    If unset will append /** to every search path unless an explicit complete path to an iso or index.bdmv is provided (in which case it is ignored)
    ''')
    group.add_argument('-i', '--iso', action='store_true', default=False,
                       help='Search for ISO files instead of index.bdmv')
    group.add_argument('-e', '--extension', nargs='*', action='append',
                       help='Search for files with the specified extension(s)')
    group.add_argument('--min-duration', type=int, default=30,
                       help='Minimum playlist duration in minutes to be considered a main title or measurement candidate')
    group.add_argument('--main-by-libbluray', action='store_true', default=True,
                       help='Finds main titles via the libbluray algorithm, this is the default algorithm')
    group.add_argument('--no-main-by-libbluray', action='store_const', const='False', dest='main_by_libbluray',
                       help='Disables use of the libbluray algorithm')
    group.add_argument('--main-by-duration', action='store_true', default=False,
                       help='Finds the main title by comparing playlist duration only (as per LAVSplitter BDDemuxer)')
    group.add_argument('--main-by-mpc-be', action='store_true', default=False,
                       help='Finds the main title via the mpc-be HdmvClipInfo algorithm')
    group.add_argument('--main-by-jriver', action='store_true', default=False,
                       help='Finds the main title via the JRiver algorithm')
    group.add_argument('--main-by-jriver-extended', action='store_true', default=False,
                       help='Extends the JRiver algorithm by resolving conflicts by title duration')
    group.add_argument('--include-hd', action='store_true', default=False,
                       help='Extend search to cover non UHD BDs')

    group = arg_parser.add_argument_group('Measure')
    group.add_argument('-f', '--force', action='store_true', default=False,
                       help='if a playlist measurement file already exists, overwrite it from index.bdmv anyway')
    group.add_argument('-c', '--copy', action='store_true', default=False,
                       help='Copies index.bdmv.measurements to the specified main title location')
    group.add_argument('-m', '--measure', action='store_true', default=False,
                       help='Calls madMeasureHDR.exe if no measurement file exists and the main title is a UHD')
    group.add_argument('--mad-measure-path', action=EnvDefault, required=False, envvar='MAD_MEASURE_HDR_PATH',
                       help='Path to madMeasureHDR.exe (can set via MAD_MEASURE_HDR_PATH env var)')
    group.add_argument('--measure-all-playlists', action='store_true', default=False,
                       help='Use with -m to also measure playlists longer than min-duration')

    group = arg_parser.add_argument_group('Output')
    group.add_argument('-v', '--verbose', action='count',
                       help='''
        Output additional logging
        Can be added multiple times
        Use -vvv to see additional debug logging from libbluray
        ''')
    group.add_argument('-s', '--silent', action='store_true', default=False,
                       help='Print the main title name only (NB: only make sense when searching for one title)')
    group.add_argument('--analyse-main-algos', action='store_true', default=False,
                       help='Produces a report showing which titles are determined as the main title')
    group.add_argument('--dry-run', action='store_true', default=False,
                       help='Execute without changing any files')
    group.add_argument('--bd-debug-mask',
                       help='Specifies a debug mask to be passed as BD_DEBUG_MASK for libbluray')
    group.add_argument('--describe-bd', action='store_true', default=False,
                       help='Outputs a description of the disc in YAML format to the BD folder directory')

    parsed_args = arg_parser.parse_args(sys.argv[1:])
    os.environ['BD_DEBUG_MASK'] = '0x0'
    if parsed_args.verbose is None or parsed_args.verbose == 0:
        main_logger.setLevel(logging.ERROR)
    elif parsed_args.verbose == 1:
        main_logger.setLevel(logging.WARNING)
    elif parsed_args.verbose == 2:
        main_logger.setLevel(logging.INFO)
    else:
        main_logger.setLevel(logging.DEBUG)
        os.environ['BD_DEBUG_MASK'] = '0x00140'

    if parsed_args.bd_debug_mask is not None:
        main_logger.info(f"Overriding BD_DEBUG_MASK - {parsed_args.bd_debug_mask}")
        os.environ['BD_DEBUG_MASK'] = parsed_args.bd_debug_mask

    file_types = []
    if parsed_args.iso is True:
        file_types.append('*.iso')
    else:
        if parsed_args.extension is not None and len(parsed_args.extension) > 0:
            for e in parsed_args.extension:
                file_types.append(f"*.{e}")
        else:
            file_types.append('BDMV/index.bdmv')

    if parsed_args.analyse_main_algos:
        csv_handler = logging.FileHandler('report/main_report.csv', mode='w+')
        csv_formatter = logging.Formatter('%(message)s')
        csv_handler.setFormatter(csv_formatter)
        csv_logger.addHandler(csv_handler)
        csv_logger.addHandler(output_handler)
        csv_logger.error('BD,Duration,MPC-BE,libbluray,jriver,jriver-extended,Count')

    for p in parsed_args.paths:
        for file_type in file_types:
            search_path(p, parsed_args, file_type)


if __name__ == '__main__':
    main()
