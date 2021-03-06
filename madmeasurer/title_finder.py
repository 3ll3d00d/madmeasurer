import os

from bluread.objects import TicksToTuple

from madmeasurer.loggers import main_logger


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
        'jriver': bd.GetTitle(get_main_title_by_jriver(bd, bd_folder_path)).Playlist
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
    if args.main_by_jriver_minute_resolution is True:
        main_titles.append(get_main_title_by_jriver(bd, bd_folder_path, resolution='minutes'))
    return {x: bd.GetTitle(x) for x in main_titles}


def get_main_title_by_jriver(bd, bd_folder_path, resolution='seconds'):
    '''
    Locates the main title using JRiver's algorithm which compares entries one by one by duration, audio stream count
    and then playlist name albeit allowing a slightly (within 10%) shorter track with more audio streams to still win.
    :param bd: the pybluread BD.
    :param bd_folder_path: the folder path.
    :param resolution: the resolution to use when comparison durations.
    :return: the main title.
    '''
    candidate_titles = __read_playlists_from_disc_inf(bd, bd_folder_path)
    if len(candidate_titles) == 0:
        candidate_titles = {x: bd.GetTitle(x) for x in range(bd.NumberOfTitles)}

    max_audio_titles = 0
    main_title = None
    main_title_num = 0

    for title_num, title in candidate_titles.items():
        new_main = False
        reason = ''
        if main_title is None:
            new_main = True
        else:
            audio_titles = __get_max_audio(title)
            cmp = 0
            if title.Length >= (main_title.Length*0.9):
                cmp = audio_titles - max_audio_titles

            if cmp == 0:
                this_len = TicksToTuple(title.Length)
                main_len = TicksToTuple(main_title.Length)
                if resolution == 'minutes':
                    cmp = ((this_len[0] * 60) + this_len[1]) - ((main_len[0] * 60) + main_len[1])
                elif resolution == 'seconds':
                    cmp = ((this_len[0] * 60 * 60) + (this_len[1] * 60) + this_len[2]) \
                          - ((main_len[0] * 60 * 60) + (main_len[1] * 60) + main_len[2])
                else:
                    cmp = title.Length - main_title.Length
                if cmp == 0:
                    cmp = audio_titles - max_audio_titles
                    if cmp == 0:
                        if title.Playlist < main_title.Playlist:
                            cmp = 1
                            reason = 'playlist name order'
                    else:
                        reason = 'audio stream count'
                else:
                    reason = 'duration'
            elif cmp > 0:
                reason = 'audio stream count, duration within 10%'

            if cmp > 0:
                new_main = True

        if new_main is True:
            if main_title is not None:
                main_logger.debug(f"New main title found {title.Playlist} vs {main_title.Playlist} : {reason}")
            else:
                main_logger.debug(f"Initialising main title search with {title.Playlist}")
            main_title = title
            main_title_num = title_num
            max_audio_titles = __get_max_audio(title)
        else:
            main_logger.debug(f"Main title remains {main_title.Playlist}, discarding {title.Playlist}")

    if main_title is None:
        main_logger.error(f"No main title found in {bd.Path}")

    return main_title_num


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
