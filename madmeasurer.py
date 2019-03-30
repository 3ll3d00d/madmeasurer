from glob import glob
import logging
import os
import sys
from pathlib import Path
import argparse
import shutil

logger = logging.getLogger('verbose')
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

output_logger = logging.getLogger('output')
output_handler = logging.StreamHandler(sys.stdout)
output_formatter = logging.Formatter('%(message)s')
output_handler.setFormatter(output_formatter)
output_logger.addHandler(output_handler)


def search_path(p, args):
    '''
    Searches for BDs to handle in the given path.
    :param p: the search path.
    :param args: the cli args.
    '''
    depth = '/**' if args.depth == -1 else ''.join(['/*'] * args.depth)
    if args.iso:
        glob_str = f"{p}{depth}/*.iso"
    else:
        glob_str = f"{p}{depth}/BDMV/index.bdmv"
    logger.info(f"Searching {glob_str}")
    for match in glob(glob_str, recursive=True):
        logger.info(f"Found {match}")
        if not args.iso:
            target = str(Path(match).parent.parent)
        else:
            target = match
        import bluread
        with bluread.Bluray(target) as b:
            b.Open(flags=0x03, min_duration=args.min_duration)
            handle_bd(b, match, target, args)


def handle_bd(b, bdmv, bdmv_root, args):
    '''
    Processes the given bd.
    :param b: the (pybluread) Bluray
    :param bdmv: the bdmv path.
    :param bdmv_root: the root directory.
    :param args: the cli args.
    '''
    main_title = get_main_title(b, args)
    main_playlist = main_title.Playlist
    logger.info(f"{bdmv} - main title is {main_playlist}")
    if args.silent:
        output_logger.error(main_playlist)
    else:
        if args.iso:
            output_logger.error(f"{bdmv_root},{main_playlist}")
        else:
            output_logger.error(f"{os.path.join(bdmv_root, 'BDMV', 'PLAYLIST', main_playlist)}")
    if args.measure is True:
        make_measurements(main_title, bdmv_root, args)
    if args.copy is True:
        copy_measurements(bdmv_root, main_playlist, args)


def get_main_title(b, args):
    '''
    Locates the main title using either the same algorithm as LAVSplitter BDDemuxer or libbluray
    '''
    if args.use_lav is True:
        main_title_idx = get_main_title_lav(b)
    else:
        main_title_idx = b.MainTitleNumber
    main_title = b.GetTitle(main_title_idx)
    return main_title


def get_main_title_lav(b):
    '''
    Locates the main title using a LAVSplitter algorithm.
    :param b: the pybluread Bluray.
    :return: the main title number.
    '''
    longest_duration = 0
    main_title_number = -1
    for title_number in range(b.NumberOfTitles):
        title = b.GetTitle(title_number)
        if title.Length > longest_duration:
            if main_title_number != -1:
                logger.info(f"Updating main title from {main_title_number} to {title_number}, duration was {longest_duration} is {title.Length}")
            main_title_number = title_number
            longest_duration = title.Length
    return main_title_number


def make_measurements(title, bdmv_root, args):
    '''
    Triggers madMeasureHDR if the title is a UHD.
    :param title: the title.
    :param bdmv_root: the bdmv root dir.
    :param args: the cli args.
    '''
    if args.measure is True:
        if title.NumberOfClips > 0:
            clip = title.GetClip(0)
            if clip is not None:
                if clip.NumberOfVideosPrimary > 0:
                    video = clip.GetVideo(0)
                    if video is not None:
                        if video.Format == '2160p':
                            logger.error(f"TODO implement measurement of {bdmv_root}")
                            pass
                        else:
                            logger.info(f"Ignoring video {bdmv_root}, format is {video.Format}")
                    else:
                        logger.error(f"{bdmv_root} main title clip 0 video 0 is None")
                else:
                    logger.error(f"{bdmv_root} main title clip 0 has no videos")
            else:
                logger.error(f"{bdmv_root} main title clip 0 is None")
        else:
            logger.warning(f"{bdmv_root} main title has no clips")
    else:
        logger.debug(f"measure flag not set, ignoring {bdmv_root}")


def copy_measurements(bdmv_root, main_playlist, args):
    '''
    Copies the index.bdmv measurements file to the correct for the main title.
    :param bdmv_root: the bdmv directory.
    :param main_playlist: the main playlist file name.
    :param args: the cli args.
    '''
    measure_src = os.path.join(bdmv_root, 'BDMV', 'index.bdmv.measurements')
    measure_dest = os.path.join(bdmv_root, 'BDMV', 'PLAYLIST', f"{main_playlist}.measurements")
    copy_it = False
    if os.path.exists(measure_src):
        if os.path.exists(measure_dest):
            if args.force is True:
                logger.info(f"Overwriting {measure_src} -> {measure_dest} as force=False")
                copy_it = True
            else:
                logger.info(f"Ignoring {measure_src} , {measure_dest} exists and force=False")
        else:
            copy_it = True
            logger.info(f"Creating {measure_src} -> {measure_dest}")
    else:
        logger.info(f"Ignoring {measure_src}, does not exist")
    if copy_it:
        logger.warning(f"Copying {measure_src} to {measure_dest}")
        shutil.copy2(measure_src, measure_dest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='madmeasurer for BDMV')
    parser.add_argument('paths', default=[os.getcwd()], nargs='+',
                        help='Path to search (for index.bdmv files)')
    parser.add_argument('-v', '--verbose', action='count',
                        help='Output additional logging, can be added multiple times, use -vvv to see additional debug logging from libbluray')
    parser.add_argument('-f', '--force', action='store_true', default=False,
                        help='if a playlist measurement file already exists, overwrite it from index.bdmv anyway')
    parser.add_argument('-c', '--copy', action='store_true', default=False,
                        help='Copies index.bdmv.measurements to the specified main title location')
    parser.add_argument('-m', '--measure', action='store_true', default=False,
                        help='Calls madMeasureHDR.exe if no measurement file exists and the main title is a UHD')
    parser.add_argument('-d', '--depth', type=int, default=-1,
                        help='Maximum folder search depth, if unset will append /** to every search path')
    parser.add_argument('-i', '--iso', action='store_true', default=False,
                        help='Search for ISO files instead of index.bdmv')
    parser.add_argument('--min-duration', type=int, default=30,
                        help='Minimum playlist duration in minimums to be considered a main title')
    parser.add_argument('-s', '--silent', action='store_true', default=False,
                        help='Print the main title name only (NB: only make sense when searching for one title)')
    parser.add_argument('--use-lav', action='store_true', default=False,
                        help='Finds the main title using the same algorithm as LAVSplitter (longest duration)')
    parsed_args = parser.parse_args(sys.argv[1:])

    valid_args = True
    if parsed_args.iso is True:
        if parsed_args.copy is True:
            print('--copy is not supported with --iso')
        if parsed_args.measure is True:
            print('--measure is not supported with --iso')

    if valid_args is True:
        if parsed_args.verbose is None or parsed_args.verbose == 0:
            logger.setLevel(logging.ERROR)
        elif parsed_args.verbose == 1:
            logger.setLevel(logging.WARNING)
        elif parsed_args.verbose == 2:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.DEBUG)
            os.environ['BD_DEBUG_MASK'] = '0x00140'

        for p in parsed_args.paths:
            search_path(p, parsed_args)
