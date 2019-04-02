from contextlib import contextmanager
from glob import glob
import logging
import os
import sys
import subprocess
import platform
from pathlib import Path
import argparse
import shutil

logger = logging.getLogger('verbose')
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(message)s')
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
        if len(p) > 4 and p[-4:] == '.iso' and '*' not in p:
            glob_str = p
        else:
            glob_str = f"{p}{depth}/*.iso"
    else:
        if len(p) > 15 and p[-15:] == 'BDMV/index.bdmv' and '*' not in p:
            glob_str = p
        elif len(p) > 5 and p[-5:] == '.m2ts' and '*' not in p:
            glob_str = p
        else:
            glob_str = f"{p}{depth}/BDMV/index.bdmv"
    logger.info(f"Searching {glob_str}")
    for match in glob(glob_str, recursive=True):
        logger.info(f"Found {match}")
        target = match if args.iso is True else str(Path(match).parent.parent)
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
    if is_uhd(bdmv_root, main_title) or args.include_hd is True:
        if args.silent:
            output_logger.error(main_playlist)
        else:
            if args.iso:
                output_logger.error(f"{bdmv_root},{main_playlist}")
            else:
                output_logger.error(f"{os.path.join(bdmv_root, 'BDMV', 'PLAYLIST', main_playlist)}")
        if args.measure is True:
            do_measure_if_necessary(bdmv, bdmv_root, args)
        if args.copy is True:
            copy_measurements(bdmv_root, main_playlist, args)
    else:
        logger.info(f"Ignoring non UHD BD - {bdmv_root}")


def is_uhd(bdmv_root, title):
    '''
    determines if the disc is a UHD
    :return: true if UHD, false if not.
    '''
    is_uhd = False
    if title.NumberOfClips > 0:
        clip = title.GetClip(0)
        if clip is not None:
            if clip.NumberOfVideosPrimary > 0:
                video = clip.GetVideo(0)
                if video is not None:
                    is_uhd = video.Format == '2160p'
                else:
                    logger.error(f"Unable to determine if {bdmv_root} is a UHD; main title clip 0 video 0 = None")
            else:
                logger.error(f"Unable to determine if {bdmv_root} is a UHD; main title clip 0 has no videos")
        else:
            logger.error(f"Unable to determine if {bdmv_root} is a UHD; main title clip 0 is None")
    else:
        logger.error(f"Unable to determine if {bdmv_root} is a UHD; main title has no clips")
    return is_uhd


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
                logger.info(
                    f"Updating main title from {main_title_number} to {title_number}, duration was {longest_duration} is {title.Length}")
            main_title_number = title_number
            longest_duration = title.Length
    return main_title_number


def do_measure_if_necessary(bdmv, bdmv_root, args):
    '''
    Triggers madMeasureHDR if the title is a UHD.
    :param bdmv_root: the bdmv root dir.
    :param args: the cli args.
    '''
    measure_src, _ = get_measurement_files(bdmv_root, None, args)
    trigger_it = False
    if os.path.exists(measure_src):
        if args.force is True:
            logger.warning(f"{measure_src} exists but force is true so remeasuring")
            trigger_it = True
        else:
            logger.info(f"{measure_src} exists and force is false, ignoring")
    else:
        logger.info(f"{measure_src} does not exist, measuring")
        trigger_it = True
    if trigger_it:
        do_measure(bdmv, args)


@contextmanager
def mount_if_necessary(iso, args):
    '''
    A context manager that can mount and iso and return the mounted path then dismounts afterwards.
    '''
    target = iso
    if args.iso is True:
        if platform.system() == "Windows":
            target = mount_iso_on_windows(iso)
        elif platform.system() == "Linux":
            pass
    try:
        yield target
    finally:
        if args.iso is True:
            if platform.system() == "Windows":
                dismount_iso_on_windows(iso)
            elif platform.system() == "Linux":
                pass


def mount_iso_on_windows(iso):
    '''
    Mounts ISO and returns the mounted drive path.
    :param iso: the iso.
    :return: the mounted path.
    '''
    command = f"PowerShell ((Mount-DiskImage {iso} -Access ReadWrite -PassThru) | Get-Volume).DriveLetter"
    logger.info(f"Triggering : {command}")
    result = subprocess.run(command, capture_output=True)
    if result is not None and result.returncode == 0:
        target = f"{result.stdout.decode('utf-8').rstrip()}:"
        logger.info(f"Mounted {iso} on {target}")
    else:
        logger.error(f"Unable to mount {iso} , stdout: {result.stdout.decode('utf-8')}, stderr: {result.stderr.decode('utf-8')}")
        target = None
    return target


def dismount_iso_on_windows(iso):
    '''
    Dismounts the ISO.
    :param iso: the iso.
    '''
    command = f"PowerShell Dismount-DiskImage {iso}"
    logger.info(f"Triggering : {command}")
    result = subprocess.run(command, capture_output=True)
    if result is not None and result.returncode == 0:
        logger.info(f"Dismounted {iso}")
    else:
        logger.error(f"Unable to dismount {iso} , stdout: {result.stdout.decode('utf-8')}, stderr: {result.stderr.decode('utf-8')}")


def do_measure(bdmv, args):
    '''
    Actually triggers madMeasureHDR and bridges the stdout back to this process stdout live
    '''
    with mount_if_necessary(bdmv, args) as measure_target:
        exe = "" if args.mad_measure_path is None else f"{args.mad_measure_path}{os.path.sep}"
        command = [os.path.abspath(f"{exe}madMeasureHDR.exe"), os.path.abspath(measure_target)]
        if args.dry_run is True:
            logger.error(f"DRY RUN! Triggering : {command}")
        else:
            logger.info(f"Triggering : {command}")
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            line_num = 0
            output = None
            tmp_output = None
            while True:
                if line_num == 0:
                    output = process.stdout.readline().decode('utf-8')
                    line_num = 1
                elif line_num == 1:
                    tmp = process.stdout.read(1)
                    if tmp == b'\x08':
                        output = tmp_output
                        tmp_output = ''
                    elif tmp == b'':
                        output = tmp_output
                        tmp_output = ''
                    else:
                        tmp_output = tmp_output + tmp.decode('utf-8')
                if output is not None:
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        output_logger.error(output.strip())
                output = None
            rc = process.poll()
            if rc == 0:
                logger.error(f"Completed OK {command}")
            else:
                logger.error(f"FAILED {command}")
        import time
        time.sleep(60)


def get_measurement_files(bdmv_root, main_playlist, args):
    '''
    Gets the measurement files (source and destination)
    '''
    if args.iso is True:
        return get_measurement_files_for_iso(bdmv_root, main_playlist)
    else:
        return get_measurement_files_for_folder(bdmv_root, main_playlist)


def get_measurement_files_for_folder(bdmv_root, main_playlist):
    '''
    Gets the measurement files (source and destination) for a BDMV folder.
    '''
    measure_src = os.path.join(bdmv_root, 'BDMV', 'index.bdmv.measurements')
    measure_dest = os.path.join(bdmv_root, 'BDMV', 'PLAYLIST', f"{main_playlist}.measurements")
    return measure_src, measure_dest


def get_measurement_files_for_iso(bdmv_root, main_playlist):
    '''
    Gets the measurement files (source and destination) for an ISO file.
    '''
    measure_src = f"{bdmv_root}[!BDMV!index.bdmv].measurements"
    measure_dest = f"{bdmv_root}[!BDMV!PLAYLIST!{main_playlist}].measurements"
    return measure_src, measure_dest


def copy_measurements(bdmv_root, main_playlist, args):
    '''
    Copies the index.bdmv measurements file to the correct for the main title.
    :param bdmv_root: the bdmv directory or iso file name.
    :param main_playlist: the main playlist file name.
    :param args: the cli args.
    '''
    measure_src, measure_dest = get_measurement_files(bdmv_root, main_playlist, args)
    copy_it = False
    if os.path.exists(measure_src):
        if os.path.exists(measure_dest):
            if args.force is True:
                logger.info(f"Overwriting {measure_src} -> {measure_dest} as force=True")
                copy_it = True
            else:
                logger.info(f"Ignoring {measure_src} , {measure_dest} exists and force=False")
        else:
            copy_it = True
            logger.info(f"Creating {measure_src} -> {measure_dest}")
    else:
        logger.info(f"Ignoring {measure_src}, does not exist")
    if copy_it:
        if args.dry_run is True:
            logger.warning(f"DRY RUN! Copying {measure_src} to {measure_dest}")
        else:
            logger.warning(f"Copying {measure_src} to {measure_dest}")
            shutil.copy2(measure_src, measure_dest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='madmeasurer for BDMV')
    parser.add_argument('paths', default=[os.getcwd()], nargs='+',
                        help='Path to search (for index.bdmv files)')

    group = parser.add_argument_group('Search')
    group.add_argument('-d', '--depth', type=int, default=-1,
                       help='''
Maximum folder search depth
If unset will append /** to every search path unless an explicit complete path to an iso or index.bdmv is provided (in which case it is ignored)
''')
    group.add_argument('-i', '--iso', action='store_true', default=False,
                       help='Search for ISO files instead of index.bdmv')
    group.add_argument('--min-duration', type=int, default=30,
                       help='Minimum playlist duration in minimums to be considered a main title')
    group.add_argument('--use-lav', action='store_true', default=False,
                       help='Finds the main title using the same algorithm as LAVSplitter (longest duration)')
    group.add_argument('--include-hd', action='store_true', default=False,
                       help='Extend search to cover non UHD BDs')

    group = parser.add_argument_group('Measure')
    group.add_argument('-f', '--force', action='store_true', default=False,
                       help='if a playlist measurement file already exists, overwrite it from index.bdmv anyway')
    group.add_argument('-c', '--copy', action='store_true', default=False,
                       help='Copies index.bdmv.measurements to the specified main title location')
    group.add_argument('-m', '--measure', action='store_true', default=False,
                       help='Calls madMeasureHDR.exe if no measurement file exists and the main title is a UHD')
    group.add_argument('--mad-measure-path', help='Path to madMeasureHDR.exe')

    group = parser.add_argument_group('Output')
    group.add_argument('-v', '--verbose', action='count',
                       help='''
    Output additional logging
    Can be added multiple times
    Use -vvv to see additional debug logging from libbluray
    ''')
    group.add_argument('--dry-run', action='store_true', default=False,
                       help='Execute without changing any files')
    group.add_argument('-s', '--silent', action='store_true', default=False,
                       help='Print the main title name only (NB: only make sense when searching for one title)')
    group.add_argument('-o', '--output-mode', default='ALL', choices=['SILENT', 'LOG ONLY', 'ALL'],
                       help='''
Controls what type of output is generated
SILENT is intended for getting the main title name only for a single BD
LOG ONLY is intended for use with -v and suppresses the SILENT output
ALL outputs all content 
''')

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
