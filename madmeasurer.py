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

csv_logger = logging.getLogger('csv')


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


def search_path(path, args, match_type):
    '''
    Searches for BDs to handle in the given path.
    :param path: the search path.
    :param args: the cli args.
    :param match_type: the type of file to find.
    '''
    depth = '/**' if args.depth == -1 else ''.join(['/*'] * args.depth)

    if os.path.exists(path) and os.path.isfile(path):
        glob_str = path
        is_index_bdmv = Path(path).name == 'index.bdmv'
    else:
        if path[-1] == '/' or path[-1] == '\\':
            path = path[0:-1]
        glob_str = f"{path}{depth}/{match_type}"
        logger.info(f"Searching {glob_str}")
        is_index_bdmv = match_type == 'BDMV/index.bdmv'

    bds_processed = 0
    for match in glob(glob_str, recursive=True):
        if bds_processed > 0 and bds_processed % 10 == 0:
            logger.warning(f"Processed {bds_processed} BDs")
        target = match if not is_index_bdmv else str(Path(match).parent.parent)
        if is_index_bdmv or match_type == '*.iso':
            open_and_process_bd(args, os.path.abspath(target), is_index_bdmv)
            bds_processed = bds_processed + 1
        else:
            # TODO implement
            logger.error(f"TODO! implement support for {match_type}, ignoring {match}")

    logger.warning(f"Completed search of {glob_str}, processed {bds_processed} BD{'' if bds_processed == 1 else 's'}")


def open_and_process_bd(args, target, is_bdmv):
    '''
    Opens the BD with libbluray and processes it.
    :param args: the cli args.
    :param match: the full path to the matched file.
    :param target: the path to the root of the BD.
    :param is_bdmv: true if the search target was an index.bdmv
    '''
    import bluread
    logger.info(f"Opening {target}")
    with bluread.Bluray(target) as bd:
        bd.Open(flags=0x03, min_duration=args.min_duration * 60)
        process_bd(bd, is_bdmv, args)
    logger.info(f"Closing {target}")


def process_bd(bd, is_bdmv, args):
    '''
    Processes the given bd.
    :param bd: the (pybluread) Bluray
    :param is_bdmv: true if the search target was an index.bdmv
    :param args: the cli args.
    '''
    with mount_if_necessary(bd.Path, args) as bd_folder_path:
        if args.measure is True or args.copy is True:
            process_measurements(bd, bd_folder_path, args)
        elif args.analyse_main_algos is True:
            m1 = bd.GetTitle(get_main_title_by_duration(bd)).Playlist
            m2 = bd.GetTitle(get_main_title_by_mpc_be(bd, bd_folder_path)).Playlist
            m3 = bd.GetTitle(bd.MainTitleNumber).Playlist
            csv_logger.error(f"\"{bd.Path}\",{m1},{m2},{m3},{m1 != m2},{m2 != m3},{m1 != m3},{m1 != m2 or m2 != m3 or m1 != m3}")
        else:
            main_title, _ = get_main_title(bd, bd_folder_path, args)
            main_playlist = main_title.Playlist
            if is_uhd(bd.Path, main_title) or args.include_hd is True:
                if args.silent:
                    output_logger.error(main_playlist)
                else:
                    if is_bdmv is True:
                        output_logger.error(f"{os.path.abspath(os.path.join(bd.Path, 'BDMV', 'PLAYLIST', main_playlist))}")
                    else:
                        output_logger.error(f"{os.path.abspath(bd.Path)},{main_playlist}")
            else:
                logger.info(f"Ignoring non UHD BD - {bd.Path}")


def process_measurements(bd, bd_folder_path, args):
    '''
    Creates measurement files by measuring or copying as necessary for the requested titles.
    :param bd: the libbluray Bluray wrapper.
    :param bd_folder_path: the physical path to the bd folder.
    :param args: the cli args
    '''
    main_title, main_title_idx = get_main_title(bd, bd_folder_path, args)
    if args.measure is True:
        for title_number in range(bd.NumberOfTitles):
            measure_it = False
            title = bd.GetTitle(title_number)
            if is_uhd(bd.Path, title):
                if title_number == main_title_idx:
                    measure_it = True
                    logger.debug(f"Measurement candidate {bd.Path} - {title.Playlist} : main title")
                elif args.measure_all_playlists is True:
                    from bluread.objects import TicksToTuple
                    title_duration = TicksToTuple(title.Length)
                    title_duration_mins = (title_duration[0] * 60) + title_duration[1]
                    if title_duration_mins >= args.min_duration:
                        logger.info(f"Measurement candidate {bd.Path} - {title.Playlist} : length is {title.LengthFancy}")
                        measure_it = True
                if measure_it is True:
                    do_measure_if_necessary(bd_folder_path, title.Playlist, args)
                else:
                    logger.debug(f"No measurement required for {bd.Path} - {title.Playlist}")
            else:
                logger.debug(f"Ignoring non uhd title {bd.Path} - {title.Playlist}")

    if args.copy is True:
        copy_measurements(bd.Path, main_title.Playlist, args)


def is_uhd(bdmv_root, title):
    '''
    determines if the disc is a UHD
    :return: true if UHD, false if not.
    '''
    is_uhd = False
    error = ''

    if title.NumberOfClips > 0:
        clip = title.GetClip(0)
        if clip is not None:
            if clip.NumberOfVideosPrimary > 0:
                video = clip.GetVideo(0)
                if video is not None:
                    is_uhd = video.Format == '2160p'
                else:
                    error = 'main title clip 0 video 0 = None'
            else:
                error = 'main title clip 0 has no videos'
        else:
            error = 'main title clip 0 is None'
    else:
        error = 'main title has no clips'

    if error != '':
        logger.error(f"Unable to determine if {bdmv_root} - {title.Playlist} is a UHD; {error}")
    return is_uhd


def get_main_title(bd, bd_folder_path, args):
    '''
    Locates the main title using either the same algorithm as LAVSplitter BDDemuxer or libbluray
    '''
    if args.main_by_duration is True:
        main_title_idx = get_main_title_by_duration(bd)
    elif args.main_by_mpc_be is True:
        main_title_idx = get_main_title_by_mpc_be(bd, bd_folder_path)
    else:
        main_title_idx = bd.MainTitleNumber
    main_title = bd.GetTitle(main_title_idx)
    return main_title, main_title_idx


def get_main_title_by_mpc_be(bd, bd_folder_path):
    '''
    Locates the main using the MPC-BE algorithm.
    :param bd: the pyblueread Bluray.
    :param bd_folder_path: the path to the bd folder.
    :return: the main title number.
    '''
    main_title_number = -1
    max_duration = 0
    max_duration_fancy = ''
    max_video_res = 0
    max_playlist_file_size = 0
    for title_number in range(bd.NumberOfTitles):
        title = bd.GetTitle(title_number)
        video_res = get_max_video_resolution(title)
        playlist_file_size = get_playlist_file_size(bd_folder_path, title)
        if (
                (title.Length > max_duration and video_res >= max_video_res)
                or (title.Length == max_duration and playlist_file_size > max_playlist_file_size)
                or ((max_duration > title.Length > max_duration / 2) and video_res > max_video_res)
        ):
            if main_title_number != -1:
                logger.info(f"Updating main title from {main_title_number} to {title_number}")
                logger.info(f"   duration:  {max_duration_fancy} -> {title.LengthFancy}")
                logger.info(f"   video_res: {max_video_res} -> {video_res}")
                logger.info(f"   file_size: {max_playlist_file_size} -> {playlist_file_size}")
            main_title_number = title_number
            max_duration = title.Length
            max_duration_fancy = title.LengthFancy
            max_video_res = video_res
            max_playlist_file_size = playlist_file_size

    return main_title_number


def get_playlist_file_size(root_path, title):
    '''
    Finds the playlist file and gets the size.
    :param root_path: the root of the bd folder.
    :param title: the title.
    :return: the file size.
    '''
    return os.path.getsize(os.path.abspath(os.path.join(root_path, 'BDMV', 'PLAYLIST', title.Playlist)))


def get_max_video_resolution(title):
    '''
    Grabs the max video resolution from the title.
    :param title: the title.
    :return: the video resolution.
    '''
    video_format = 0
    if title.NumberOfClips > 0:
        for clip_num in range(title.NumberOfClips):
            clip = title.GetClip(clip_num)
            if clip is not None and clip.NumberOfVideosPrimary > 0:
                for vid_num in range(clip.NumberOfVideosPrimary):
                    video = clip.GetVideo(vid_num)
                    if video is not None:
                        video_format = max(video_format, int(video.Format[:-1]))
    return video_format


def get_main_title_by_duration(b):
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


@contextmanager
def mount_if_necessary(bd_path, args):
    '''
    A context manager that can mount and iso and return the mounted path then dismounts afterwards.
    '''
    target = bd_path
    mounted = False
    if args.measure is True or args.copy is True or args.main_by_mpc_be is True or args.analyse_main_algos is True:
        mounted = target[-4:] == '.iso'
        if mounted is True:
            if platform.system() == "Windows":
                target = mount_iso_on_windows(bd_path)
                if target is not None:
                    if not os.path.exists(f"{target}BDMV/index.bdmv"):
                        logger.error(f"{bd_path} does not contain a BD folder")
                        target = None
            elif platform.system() == "Linux":
                pass
    try:
        yield target
    finally:
        if mounted:
            if platform.system() == "Windows":
                dismount_iso_on_windows(bd_path)
            elif platform.system() == "Linux":
                pass


def mount_iso_on_windows(iso):
    '''
    Mounts ISO and returns the mounted drive path.
    :param iso: the iso.
    :return: the mounted path.
    '''
    iso_to_mount = os.path.abspath(iso)
    command = f"PowerShell ((Mount-DiskImage {iso_to_mount} -PassThru) | Get-Volume).DriveLetter"
    logger.debug(f"Triggering : {command}")
    result = subprocess.run(command, capture_output=True)
    if result is not None and result.returncode == 0:
        target = f"{result.stdout.decode('utf-8').rstrip()}:{os.path.sep}"
        logger.info(f"Mounted {iso_to_mount} on {target}")
    else:
        logger.error(f"Unable to mount {iso_to_mount} , stdout: {result.stdout.decode('utf-8')}, stderr: {result.stderr.decode('utf-8')}")
        target = None
    return target


def dismount_iso_on_windows(iso):
    '''
    Dismounts the ISO.
    :param iso: the iso.
    '''
    iso_to_dismount = os.path.abspath(iso)
    command = f"PowerShell Dismount-DiskImage {iso_to_dismount}"
    logger.debug(f"Triggering : {command}")
    result = subprocess.run(command, capture_output=True)
    if result is not None and result.returncode == 0:
        logger.info(f"Dismounted {iso_to_dismount}")
    else:
        logger.error(f"Unable to dismount {iso_to_dismount} , stdout: {result.stdout.decode('utf-8')}, stderr: {result.stderr.decode('utf-8')}")


def do_measure_if_necessary(bd_folder_path, playlist, args):
    '''
    Triggers madMeasureHDR if the title is a UHD and the measurements file for the playlist does not exist.
    :param bd_folder_path: the bdmv root dir.
    :param args: the cli args.
    '''
    playlist_file = os.path.join(bd_folder_path, 'BDMV', 'PLAYLIST', playlist)
    measurement_file = f"{playlist_file}.measurements"
    trigger_it = False
    if os.path.exists(measurement_file):
        if args.force is True:
            logger.warning(f"Remeasuring : {measurement_file} exists, force is true")
            trigger_it = True
        else:
            logger.info(f"Ignoring : {measurement_file} exists, force is false")
    else:
        logger.info(f"Measuring : {measurement_file} does not exist")
        trigger_it = True
    if trigger_it:
        run_mad_measure_hdr(playlist_file, args)


def run_mad_measure_hdr(measure_target, args):
    '''
    triggers madMeasureHDR and bridges the stdout back to this process stdout live
    :param args: the cli args.
    :param measure_target: file to measure.
    '''
    exe = "" if args.mad_measure_path is None else f"{args.mad_measure_path}{os.path.sep}"
    command = [os.path.abspath(f"{exe}madMeasureHDR.exe"), os.path.abspath(measure_target)]
    if args.dry_run is True:
        logger.error(f"DRY RUN! Triggering : {command}")
    else:
        logger.info(f"Triggering : {command}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=4)
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


def copy_measurements(bd_folder_path, main_playlist, args):
    '''
    Copies an existing index.bdmv measurements file to the correct location for the main title.
    :param bd_folder_path: the bd folder path.
    :param main_playlist: the main playlist file name.
    :param args: the cli args.
    '''
    src_file = os.path.join(bd_folder_path, 'BDMV', 'index.bdmv.measurements')
    dest_file = os.path.join(bd_folder_path, 'BDMV', 'PLAYLIST', f"{main_playlist}.measurements")
    copy_it = False
    if os.path.exists(src_file):
        if os.path.exists(dest_file):
            if args.force is True:
                logger.info(f"Overwriting : {src_file} with {dest_file} as force=True")
                copy_it = True
            else:
                logger.info(f"Ignoring : {dest_file} exists and force=False")
        else:
            copy_it = True
            logger.info(f"Creating : {src_file} -> {dest_file}")
    else:
        logger.info(f"Ignoring : {src_file}, does not exist")
    if copy_it:
        if args.dry_run is True:
            logger.warning(f"DRY RUN! Copying {src_file} to {dest_file}")
        else:
            logger.warning(f"Copying {src_file} to {dest_file}")
            shutil.copy2(src_file, dest_file)
            logger.warning(f"Copied {src_file} to {dest_file}")


if __name__ == '__main__':
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
    group.add_argument('--main-by-duration', action='store_true', default=False,
                       help='Finds the main title by comparing playlist duration only (as per LAVSplitter BDDemuxer)')
    group.add_argument('--main-by-mpc-be', action='store_true', default=False,
                       help='Finds the main title via the mpc-be HdmvClipInfo algorithm')
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

    parsed_args = arg_parser.parse_args(sys.argv[1:])
    os.environ['BD_DEBUG_MASK'] = '0x0'
    if parsed_args.verbose is None or parsed_args.verbose == 0:
        logger.setLevel(logging.ERROR)
    elif parsed_args.verbose == 1:
        logger.setLevel(logging.WARNING)
    elif parsed_args.verbose == 2:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)
        os.environ['BD_DEBUG_MASK'] = '0x00140'

    if parsed_args.bd_debug_mask is not None:
        logger.info(f"Overriding BD_DEBUG_MASK - {parsed_args.bd_debug_mask}")
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
        csv_handler = logging.FileHandler('main_report.csv', mode='w+')
        csv_formatter = logging.Formatter('%(message)s')
        csv_handler.setFormatter(csv_formatter)
        csv_logger.addHandler(csv_handler)
        csv_logger.addHandler(output_handler)
        csv_logger.error('BD,Duration,MPC-BE,libbluray,Diff 1-2,Diff 2-3,Diff 1-3,Any Diff')

    for p in parsed_args.paths:
        for file_type in file_types:
            search_path(p, parsed_args, file_type)
