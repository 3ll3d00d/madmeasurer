import os
import shutil
import subprocess
from glob import glob
from pathlib import Path

from madmeasurer.helpers import mount_if_necessary
from madmeasurer.title_finder import get_main_titles, get_main_title_by_duration, get_main_title_by_mpc_be, \
    get_main_title_by_jriver
from madmeasurer.describe import describe_bd


def search_path(path, args, match_type, depth):
    '''
    Searches for BDs to handle in the given path.
    :param path: the search path.
    :param args: the cli args.
    :param match_type: the type of file to find.
    :param the search depth:
    '''
    from madmeasurer.loggers import main_logger
    depth = '/**' if depth == -1 else ''.join(['/*'] * depth)
    if os.path.exists(path) and os.path.isfile(path):
        glob_str = path
        is_index_bdmv = Path(path).name == 'index.bdmv'
    else:
        if path[-1] == '/' or path[-1] == '\\':
            path = path[0:-1]
        glob_str = f"{path}{depth}/{match_type}"
        main_logger.info(f"Searching {glob_str}")
        is_index_bdmv = match_type == 'BDMV/index.bdmv'

    match_type_desc = 'BD' if match_type == 'BDMV/index.bdmv' else match_type[2:] + ' file'
    bds_processed = 0
    for match in glob(glob_str, recursive=True):
        if bds_processed > 0 and bds_processed % 10 == 0:
            main_logger.warning(f"Processed {bds_processed} {match_type_desc}s")
        target = match if not is_index_bdmv else str(Path(match).parent.parent)
        if is_index_bdmv or match_type == '*.iso':
            open_and_process_bd(args, os.path.abspath(target), is_index_bdmv)
            bds_processed = bds_processed + 1
        elif match_type[2:] == 'mkv':
            process_mkv(os.path.abspath(target), args)
        else:
            main_logger.info(f"Target found for {match_type}, measuring {target}")
            do_measure_if_necessary(os.path.abspath(target), args)

    main_logger.warning(f"Completed search of {glob_str}, processed {bds_processed} {match_type_desc}{'' if bds_processed == 1 else 's'}")


def process_mkv(target, args):
    '''
    Examines the mkv with enzyme and checks if it is a UHD file.
    :param args: the cli args.
    :param target: the full path to the matched file.
    '''
    if args.include_hd is True or __is_uhd_mkv(target) is True:
        do_measure_if_necessary(target, args)
    else:
        from madmeasurer.loggers import main_logger
        main_logger.info(f"Ignoring {target}, is not UHD and include-hd is false")


def __is_uhd_mkv(target):
    with open(target, 'rb') as mkv_f:
        import enzyme
        mkv = enzyme.MKV(mkv_f)
        if len(mkv.video_tracks) > 0:
            uhd_track = next((v for v in mkv.video_tracks if v.display_width > 1920), None)
            return uhd_track is not None
    return False


def open_and_process_bd(args, target, is_bdmv):
    '''
    Opens the BD with libbluray and processes it.
    :param args: the cli args.
    :param match: the full path to the matched file.
    :param target: the path to the root of the BD.
    :param is_bdmv: true if the search target was an index.bdmv
    '''
    from madmeasurer.loggers import main_logger
    import bluread
    main_logger.info(f"Opening {target}")
    with bluread.Bluray(target) as bd:
        try:
            bd.Open(flags=0x03, min_duration=args.min_duration * 60)
            process_bd(bd, is_bdmv, args)
        except Exception as e:
            if 'Failed to get titles' in str(e):
                main_logger.info(f"{target} has no titles longer than {args.min_duration}, ignoring")
            else:
                main_logger.exception(f"Unable to read {target}, ignoring")
    main_logger.info(f"Closing {target}")


def process_bd(bd, is_bdmv, args):
    '''
    Processes the given bd.
    :param bd: the (pybluread) Bluray
    :param is_bdmv: true if the search target was an index.bdmv
    :param args: the cli args.
    '''
    from madmeasurer.loggers import main_logger, output_logger, csv_logger
    with mount_if_necessary(bd.Path, args) as bd_folder_path:
        if args.measure is True or args.copy is True:
            process_measurements(bd, bd_folder_path, args)
        elif args.analyse_main_algos is True:
            m1 = bd.GetTitle(get_main_title_by_duration(bd)).Playlist
            m2 = bd.GetTitle(get_main_title_by_mpc_be(bd, bd_folder_path)).Playlist
            m3 = bd.GetTitle(bd.MainTitleNumber).Playlist
            m4 = bd.GetTitle(get_main_title_by_jriver(bd, bd_folder_path)).Playlist
            m5 = bd.GetTitle(get_main_title_by_jriver(bd, bd_folder_path, resolution='minutes')).Playlist
            csv_logger.error(f"\"{bd.Path}\",{m1},{m2},{m3},{m4},{m5},{len({m1, m2, m3, m4, m5})}")
        else:
            main_titles = get_main_titles(bd, bd_folder_path, args).values()
            if is_any_title_uhd(bd.Path, main_titles) or args.include_hd is True:
                if args.silent:
                    for t in main_titles:
                        output_logger.error(t.Playlist)
                else:
                    for t in main_titles:
                        if is_bdmv is True:
                            output_logger.error(f"{os.path.abspath(os.path.join(bd.Path, 'BDMV', 'PLAYLIST', t.Playlist))}")
                        else:
                            output_logger.error(f"{os.path.abspath(bd.Path)},{t.Playlist}")
            else:
                main_logger.info(f"Ignoring non UHD BD - {bd.Path}")
        if args.describe_bd is True:
            describe_bd(bd, bd_folder_path, force=args.force, verbose=args.verbose is not None and args.verbose > 2)


def process_measurements(bd, bd_folder_path, args):
    '''
    Creates measurement files by measuring or copying as necessary for the requested titles.
    :param bd: the libbluray Bluray wrapper.
    :param bd_folder_path: the physical path to the bd folder.
    :param args: the cli args
    '''
    from madmeasurer.loggers import main_logger
    main_titles = get_main_titles(bd, bd_folder_path, args)
    if args.measure is True:
        for title_number in range(bd.NumberOfTitles):
            measure_it = False
            title = bd.GetTitle(title_number)
            if is_any_title_uhd(bd.Path, main_titles.values()):
                if title_number in main_titles.keys():
                    measure_it = True
                    main_logger.debug(f"Measurement candidate {bd.Path} - {title.Playlist} : main title")
                elif args.measure_all_playlists is True:
                    from bluread.objects import TicksToTuple
                    title_duration = TicksToTuple(title.Length)
                    title_duration_mins = (title_duration[0] * 60) + title_duration[1]
                    if title_duration_mins >= args.min_duration:
                        if args.max_duration is None or title_duration_mins <= args.max_duration:
                            main_logger.info(f"Measurement candidate {bd.Path} - {title.Playlist} : length is {title.LengthFancy}")
                            measure_it = True
                if measure_it is True:
                    playlist_file = os.path.join(bd_folder_path, 'BDMV', 'PLAYLIST', title.Playlist)
                    do_measure_if_necessary(playlist_file, args)
                else:
                    main_logger.debug(f"No measurement required for {bd.Path} - {title.Playlist}")
            else:
                main_logger.debug(f"Ignoring non uhd title {bd.Path} - {title.Playlist}")

    if args.copy is True:
        for t in main_titles.values():
            copy_measurements(bd.Path, t.Playlist, args)


def is_any_title_uhd(bdmv_root, titles):
    '''
    determines if the disc is a UHD
    :return: true if UHD, false if not.
    '''
    from madmeasurer.loggers import main_logger
    is_uhd = False
    error = ''
    for t in titles:
        if t.NumberOfClips > 0:
            clip = t.GetClip(0)
            if clip is not None:
                if clip.NumberOfVideosPrimary > 0:
                    video = clip.GetVideo(0)
                    if video is not None:
                        is_uhd |= video.Format == '2160p'
                    else:
                        error = 'main title clip 0 video 0 = None'
                else:
                    error = 'main title clip 0 has no videos'
            else:
                error = 'main title clip 0 is None'
        else:
            error = 'main title has no clips'

        if error != '':
            main_logger.error(f"Unable to determine if {bdmv_root} - {t.Playlist} is a UHD; {error}")
    return is_uhd


def do_measure_if_necessary(target_file, args):
    '''
    Triggers madMeasureHDR if the title is a UHD and the measurements file for the playlist does not exist.
    :param target_file: the file to measure
    :param args: the cli args.
    '''
    from madmeasurer.loggers import main_logger
    measurement_file = f"{target_file}.measurements"
    incomplete_measurements_file = f"{measurement_file}.incomplete"
    if os.path.exists(measurement_file):
        trigger_it = __should_trigger_measurement(args, measurement_file)
    elif os.path.exists(incomplete_measurements_file):
        trigger_it = __should_trigger_measurement(args, incomplete_measurements_file)
    else:
        main_logger.info(f"Measuring : {measurement_file} does not exist")
        trigger_it = True
    if trigger_it:
        run_mad_measure_hdr(target_file, args)


def __should_trigger_measurement(args, measurement_file):
    from madmeasurer.loggers import main_logger
    if args.force is True:
        main_logger.warning(f"Remeasuring : {measurement_file} exists, force is true")
        return True
    else:
        main_logger.info(f"Ignoring : {measurement_file} exists, force is false")
        return False


def run_mad_measure_hdr(measure_target, args):
    '''
    triggers madMeasureHDR and bridges the stdout back to this process stdout live
    :param args: the cli args.
    :param measure_target: file to measure.
    '''
    from madmeasurer.loggers import main_logger, output_logger
    exe = "" if args.mad_measure_path is None else f"{args.mad_measure_path}{os.path.sep}"
    command = [os.path.abspath(f"{exe}madMeasureHDR.exe"), os.path.abspath(measure_target)]
    if args.dry_run is True:
        main_logger.error(f"DRY RUN! Triggering : {command}")
    else:
        if not os.path.isfile(command[0]):
            main_logger.error(f"FAILED! madMeasureHDR.exe not found at {command[0]}")
        else:
            main_logger.info(f"Triggering : {command}")
            txt_output = os.path.abspath(f"{measure_target}-madvr.txt")
            with open(txt_output, 'w') as details:
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
                            txt = output.strip()
                            output_logger.error(txt)
                            details.write(txt + '\n')
                            details.flush()
                    output = None
                rc = process.poll()
                if rc == 0:
                    main_logger.error(f"Completed OK {command}")
                else:
                    main_logger.error(f"FAILED {command}")


def copy_measurements(bd_folder_path, main_playlist, args):
    '''
    Copies an existing index.bdmv measurements file to the correct location for the main title.
    :param bd_folder_path: the bd folder path.
    :param main_playlist: the main playlist file name.
    :param args: the cli args.
    '''
    from madmeasurer.loggers import main_logger
    src_file = os.path.join(bd_folder_path, 'BDMV', 'index.bdmv.measurements')
    dest_file = os.path.join(bd_folder_path, 'BDMV', 'PLAYLIST', f"{main_playlist}.measurements")
    copy_it = False
    if os.path.exists(src_file):
        if os.path.exists(dest_file):
            if args.force is True:
                main_logger.info(f"Overwriting : {src_file} with {dest_file} as force=True")
                copy_it = True
            else:
                main_logger.info(f"Ignoring : {dest_file} exists and force=False")
        else:
            copy_it = True
            main_logger.info(f"Creating : {src_file} -> {dest_file}")
    else:
        main_logger.info(f"Ignoring : {src_file}, does not exist")
    if copy_it:
        if args.dry_run is True:
            main_logger.warning(f"DRY RUN! Copying {src_file} to {dest_file}")
        else:
            main_logger.warning(f"Copying {src_file} to {dest_file}")
            shutil.copy2(src_file, dest_file)
            main_logger.warning(f"Copied {src_file} to {dest_file}")
