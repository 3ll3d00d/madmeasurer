import os
from collections import defaultdict

from madmeasurer.loggers import main_logger
from bluread.objects import TicksToFancy


def main_title_by_algo(bd, bd_folder_path):
    '''
    Gets the playlist determined by each algo to be the main title.
    :param bd: the bd.
    :param bd_folder_path: the folder path.
    :return: a dict
    '''
    return {
        'libbluray': bd.GetTitle(bd.MainTitleNumber).Playlist,
        'mpc-be': bd.GetTitle(get_main_title_by_mpc_be(bd, bd_folder_path)).Playlist,
        'duration': bd.GetTitle(get_main_title_by_duration(bd)).Playlist,
        'jriver': bd.GetTitle(get_main_title_by_jriver(bd, bd_folder_path)).Playlist,
        'jriver-extended': bd.GetTitle(get_main_title_by_jriver(bd, bd_folder_path, extended=True)).Playlist
    }


def get_main_titles(bd, bd_folder_path, args):
    '''
    Locates the main title via the selected algorithms as LAVSplitter BDDemuxer or libbluray
    :return: a dict o
    '''
    main_titles = []
    if args.main_by_duration is True:
        main_titles.append(get_main_title_by_duration(bd))
    if args.main_by_mpc_be is True:
        main_titles.append(get_main_title_by_mpc_be(bd, bd_folder_path))
    if args.main_by_libbluray is True:
        main_titles.append(bd.MainTitleNumber)
    if args.main_by_jriver is True:
        main_titles.append(get_main_title_by_jriver(bd, bd_folder_path))
    if args.main_by_jriver_extended is True:
        main_titles.append(get_main_title_by_jriver(bd, bd_folder_path, extended=True))
    return {x: bd.GetTitle(x) for x in main_titles}


def get_main_title_by_jriver(bd, bd_folder_path, extended=False):
    '''
    Locates the main title using JRiver's algorithm
    :param bd: the pybluread BD.
    :param bd_folder_path: the folder path.
    :param extended: if true, resolve conflicts in a less naive way.
    :return: the main title.
    '''
    candidate_titles = __read_playlists_from_disc_inf(bd, bd_folder_path)

    if len(candidate_titles) == 0:
        title_durations = {x: bd.GetTitle(x).Length for x in range(bd.NumberOfTitles)}
        max_duration = sorted(list(title_durations.values()), reverse=True)[0]
        min_duration = max_duration * 0.9
        candidate_titles = {k: bd.GetTitle(k) for k, v in title_durations.items() if v >= min_duration}
        candidate_playlists = {k: v.Playlist for k, v in candidate_titles.items()}
        main_logger.debug(f"Evaluated {bd.NumberOfTitles} titles by duration, "
                          f"range: {TicksToFancy(min_duration)} - {TicksToFancy(max_duration)}")
        main_logger.debug(f"Found {len(candidate_playlists)} candidates {str(list(candidate_playlists.values()))}")

    max_audio_titles = defaultdict(list)
    for k, v in candidate_titles.items():
        max_audio_titles[__get_max_audio(v)].append(k)
    for k, v in sorted(max_audio_titles.items(), key=lambda kv: kv[0], reverse=True):
        if len(v) > 1:
            titles = [bd.GetTitle(x) for x in v]
            if extended is True:
                final_selection = sorted(titles, key=lambda t: t.Length, reverse=True)
            else:
                final_selection = titles
            playlists = {x.Playlist: x.LengthFancy for x in final_selection}
            conflict_resolver = ' [extended]' if extended is True else ''
            main_logger.debug(f"Found {len(v)} candidates with {k} audio streams {playlists}{conflict_resolver}")
        return v[0]
    main_logger.error(f"No main title found in {bd.Path}")
    return None


def __read_playlists_from_disc_inf(bd, bd_folder_path):
    candidate_titles = {}
    if os.path.exists(os.path.join(bd_folder_path, 'disc.inf')):
        obfuscated_playlists = None
        with open(os.path.join(bd_folder_path, 'disc.inf'), mode='r') as f:
            for line in f:
                if line.startswith('playlists='):
                    obfuscated_playlists = [f"{int(x.strip()):05}.mpls" for x in line[10:].split(',')]
                    break
        if obfuscated_playlists is not None:
            main_logger.debug(f"disc.inf found with obfuscated playlists {obfuscated_playlists}")
            for x in range(bd.NumberOfTitles):
                t = bd.GetTitle(x)
                if t.Playlist in obfuscated_playlists:
                    candidate_titles[x] = t
        else:
            main_logger.debug('No playlists found in disc.inf')
    else:
        main_logger.debug('No disc.inf found')
    return candidate_titles


def __get_max_audio(title):
    '''
    Gets the maximum number of audio channels in the title.
    :param title: the title.
    :return: the count.
    '''
    return max([title.GetClip(clip_number).NumberOfAudiosPrimary for clip_number in range(title.NumberOfClips)])


def get_main_title_by_mpc_be(bd, bd_folder_path):
    '''
    Locates the main using the MPC-BE algorithm.
    :param bd: the pyblueread Bluray.
    :param bd_folder_path: the path to the bd folder.
    :return: the main title number.
    '''
    main_title_playlist = ''
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
                main_logger.info(f"Updating main title from {main_title_playlist} to {title.Playlist}")
                main_logger.info(f"   duration:  {max_duration_fancy} -> {title.LengthFancy}")
                main_logger.info(f"   video_res: {max_video_res} -> {video_res}")
                main_logger.info(f"   file_size: {max_playlist_file_size} -> {playlist_file_size}")
            main_title_number = title_number
            main_title_playlist = title.Playlist
            max_duration = title.Length
            max_duration_fancy = title.LengthFancy
            max_video_res = video_res
            max_playlist_file_size = playlist_file_size

    return main_title_number


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
                main_logger.info(
                    f"Updating main title from {main_title_number} to {title_number}, duration was {longest_duration} is {title.Length}")
            main_title_number = title_number
            longest_duration = title.Length
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
