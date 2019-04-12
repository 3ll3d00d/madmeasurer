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
                if len(default) > 0 and default[0] == '"' and default[-1] == '"':
                    default = default[1:-1]
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
    group.add_argument('-d', '--exact-depth', type=int,
                       help='Sets the search depth to the specific folder depth only, e.g. if -d 2 then search for <path>/*/*/BDMV/index.bdmv . If neither --exact-depth nor --max-depth is set then search for /** unless the path is to a specific file')
    group.add_argument('--max-depth', type=int,
                       help='Sets the maximum folder depth to search, e.g. if --max-depth 2 then search for <path>/BDMV/index.bdmv and <path>/*/BDMV/index.bdmv and <path>/*/*/BDMV/index.bdmv. If neither --exact-depth nor --max-depth is set then search for /** unless the path is to a specific file')
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
    group.add_argument('--main-by-jriver-minute-resolution', action='store_true', default=False,
                       help='Finds the main title via the JRiver algorithm using minute resolution when comparing durations')
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
                       help='Use with -m to also measure playlists longer than min-duration (and shorter than max-duration if supplied)')
    group.add_argument('--max-duration', type=int,
                       help='Maximum playlist duration in minutes for measurements candidates, applies to --measure-all-playlists only')

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
        try:
            os.mkdir('report')
        except FileExistsError:
            pass
        csv_handler = logging.FileHandler('report/main_report.csv', mode='w+')
        csv_formatter = logging.Formatter('%(message)s')
        csv_handler.setFormatter(csv_formatter)
        csv_logger.addHandler(csv_handler)
        csv_logger.addHandler(output_handler)
        csv_logger.error('BD,Duration,MPC-BE,libbluray,jriver,Count')

    if parsed_args.measure_all_playlists is True \
            and parsed_args.max_duration is not None \
            and parsed_args.max_duration <= parsed_args.min_duration:
        raise ValueError(f"--max-duration {parsed_args.max_duration} is less than --min-duration {parsed_args.min_duration}")

    for p in parsed_args.paths:
        for file_type in file_types:
            if os.path.exists(p) and os.path.isfile(p):
                search_path(p, parsed_args, file_type, 0)
            else:
                if parsed_args.exact_depth is not None or parsed_args.max_depth is not None:
                    if parsed_args.exact_depth is not None:
                        min_depth = parsed_args.exact_depth
                        max_depth = min_depth
                    else:
                        min_depth = 0
                        max_depth = parsed_args.max_depth
                    for depth in range(min_depth, max_depth + 1):
                        search_path(p, parsed_args, file_type, depth)
                else:
                    search_path(p, parsed_args, file_type, -1)


if __name__ == '__main__':
    main()
