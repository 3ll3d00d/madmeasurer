from glob import glob
import logging
import os
import sys
from pathlib import Path
import argparse
import bluread
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
    logger.info(f"Searching {p}")
    for bdmv in glob(f"{p}/**/BDMV/index.bdmv", recursive=True):
        logger.info(f"Found {bdmv}")
        bdmv_root = str(Path(bdmv).parent.parent)
        with bluread.Bluray(bdmv_root) as b:
            b.Open()
            parsing_bd(b, bdmv, bdmv_root, args)


def parsing_bd(b, bdmv, bdmv_root, args):
    main_title_idx = b.MainTitleNumber
    main_title = b.GetTitle(main_title_idx)
    main_playlist = main_title.Playlist
    logger.info(f"{bdmv} - main title is {main_playlist}")
    output_logger.error(f"{bdmv_root}/BDMV/PLAYLIST/{main_playlist}")
    if args.measure is True:
        make_measurements(main_title, bdmv_root, args)
    if args.copy is True:
        copy_measurements(bdmv_root, main_playlist, args)


def make_measurements(title, bdmv_root, args):
    if args.measure is True:
        if title.NumberOfClips > 0:
            clip = title.GetClip(0)
            if clip is not None:
                if clip.NumberOfVideosPrimary > 0:
                    video = clip.GetVideo(0)
                    if video is not None:
                        if video.Format == '8':
                            logger.error(f"TODO implement measurement of {bdmv_root}")
                            pass
                        else:
                            logger.info(f"Ignoring video {bdmv_root}, format is {'1080i' if video.Format == '4' else video.Format}")
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
    parser.add_argument('paths', default=[os.getcwd()], nargs='+', help='Path to search (for index.bdmv files)')
    parser.add_argument('-v', '--verbose', action='count', help='Output additional logging')
    parser.add_argument('-f', '--force', action='store_true', default=False,
                        help='if a playlist measurement file already exists, overwrite it from index.bdmv anyway')
    parser.add_argument('-c', '--copy', action='store_true', default=False,
                        help='Copies index.bdmv.measurements to the specified main title location')
    parser.add_argument('-m', '--measure', action='store_true', default=False,
                        help='Calls madMeasureHDR.exe if no measurement file exists and the main title is a UHD')
    parsed = parser.parse_args(sys.argv[1:])

    if parsed.verbose is None or parsed.verbose == 0:
        logger.setLevel(logging.ERROR)
    elif parsed.verbose == 1:
        logger.setLevel(logging.WARNING)
    elif parsed.verbose == 2:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)

    for p in parsed.paths:
        search_path(p, parsed)
