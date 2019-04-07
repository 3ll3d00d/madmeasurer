import os

import yaml

from madmeasurer.loggers import main_logger
from madmeasurer.title_finder import main_title_by_algo


def describe_bd(bd, bd_folder_path, force=False, verbose=False):
    '''
    Outputs a yaml file into the bd folder describing the BD.
    :param bd: the libbluray BD.
    :param bd_folder_path: the BD folder path.
    :param force: overwrite the file if it exists.
    :param verbose: if true, dump the output to the screen
    '''
    output_file = os.path.join(bd_folder_path, 'disc.yaml')
    if not os.path.exists(output_file) or force is True:
        details = {'name': bd.Path, 'title_count': bd.NumberOfTitles,
                   'main_titles': main_title_by_algo(bd, bd_folder_path)}
        titles = []
        for title_number in range(bd.NumberOfTitles):
            t = bd.GetTitle(title_number)
            title = {'idx': title_number, 'playlist': t.Playlist, 'duration_raw': t.Length, 'duration': t.LengthFancy,
                     'angle_count': t.NumberOfAngles, 'chapter_count': t.NumberOfChapters}

            chapters = []
            for chapter_number in range(1, t.NumberOfChapters + 1):
                c = t.GetChapter(chapter_number)
                chapter = {'idx': chapter_number, 'start_raw': c.Start, 'start': c.StartFancy, 'end_raw': c.End,
                           'end': c.EndFancy, 'duration_raw': c.Length, 'duration': c.LengthFancy}
                chapters.append(chapter)
            title['chapters'] = chapters

            title['clip_count'] = t.NumberOfClips
            clips = []
            for clip_number in range(t.NumberOfClips):
                c = t.GetClip(clip_number)
                clip = {'idx': clip_number, 'video_primary_count': c.NumberOfVideosPrimary}
                videos = []
                for video_number in range(c.NumberOfVideosPrimary):
                    v = c.GetVideo(video_number)
                    video = {'idx': video_number, 'language': v.Language, 'coding_type': v.CodingType,
                             'format': v.Format, 'rate': v.Rate, 'aspect': v.Aspect}
                    videos.append(video)
                clip['video_primary'] = videos

                clip['audio_primary_count'] = c.NumberOfAudiosPrimary
                audios = []
                for audio_number in range(c.NumberOfAudiosPrimary):
                    a = c.GetAudio(audio_number)
                    audio = {'idx': audio_number, 'language': a.Language, 'coding_type': a.CodingType,
                             'format': a.Format, 'rate': a.Rate}
                    audios.append(audio)
                clip['audio_primary'] = audios

                clip['subtitle_count'] = c.NumberOfSubtitles
                subtitles = []
                for subtitle_number in range(c.NumberOfSubtitles):
                    s = c.GetSubtitle(subtitle_number)
                    subtitle = {'idx': subtitle_number, 'language': s.Language}
                    subtitles.append(subtitle)
                clip['subtitles'] = subtitles
                clips.append(clip)

            title['clips'] = clips
            titles.append(title)

        details['titles'] = titles
        with open(output_file, 'w+') as f:
            yaml.dump(details, f)
            if verbose is True:
                main_logger.debug(yaml.dump(details))
