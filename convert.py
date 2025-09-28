import dataclasses
import enum
import os
import re
import shutil
import subprocess
from operator import itemgetter

from pathlib import Path
from typing import Literal, Union

import winsound

from tkinter import filedialog as fd

import time

from pydantic import validate_call

from tkinter import Tk, ttk

import tkinter

import diskcache

from pymediainfo import MediaInfo

import requests


class TuneH264(enum.Enum):
    FILM = 0
    ANIMATION = 1
    GRAIN = 2
    STILLIMAGE = 3
    FASTDECODE = 4
    ZEROLATENCY = 5


class PresetH264(enum.Enum):
    ULTRAFAST = 'ULTRAFAST'
    SUPERFAST = 'SUPERFAST'
    VERYFAST = 'VERYFAST'
    FASTER = 'FASTER'
    FAST = 'FAST'
    MEDIUM = 'MEDIUM'
    SLOW = 'SLOW'
    SLOWER = 'SLOWER'
    VERYSLOW = 'VERYSLOW'
    PLACEBO = 'PLACEBO'


class Converter:

    def __init__(self):
        self.ffmpeg_file = Path(r'C:\Users\T\AppData\Local\UniGetUI\Chocolatey\lib\ffmpeg-full\tools\ffmpeg\bin\ffmpeg.exe')

        self.script_dir = Path(__file__).parent

        self.tmp_dir = self.script_dir / 'tmp'

        self.cache = diskcache.Cache((self.tmp_dir / 'converter_cache').as_posix())

    @dataclasses.dataclass
    class ConvertResult:
        in_file: Path
        out_file: Path

    @staticmethod
    @validate_call()
    def exec_ffmpeg(args: list):
        args2 = []

        for i in args:
            if type(i) is str:
                args2.append(str(i))

            else:
                args2.append(f'"{i}"')

        cmd = ' '.join(args2)

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=False)

        (out, err) = proc.communicate()

        if out is not None:
            print(out.decode('utf-8', errors='replace'))

        if err is not None:
            print(err.decode('utf-8', errors='replace'))

            return False

        return True

    @validate_call()
    def vp9(self, file: Path = None, width: int = None, crf: int = 23, vorbis_quality: int = 7):

        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        self.exec_ffmpeg(
            [
                self.ffmpeg_file.as_posix() + ' ',
                '-i', file,
                '-row-mt', '1',
                '-c:v', 'libvpx-vp9',
                '-b:v', '0',
                '-crf', str(crf),
                '-pass', '1',
                '-vf', f'scale={width}:-1:flags=lanczos',
                '-an',
                '-f', 'null', 'NUL'
            ]
        )

        params = [
            self.ffmpeg_file.as_posix() + ' ',
            '-y',
            '-i', file,
            '-row-mt', '1',
            '-c:v', 'libvpx-vp9',
            '-c:a', 'libvorbis',
            '-qscale:a', f'{vorbis_quality}',
            '-b:v', '0',
            '-crf', str(crf),
            '-pass', '2',
        ]

        if width:
            params += ['-vf', f'scale={width}:-1:flags=lanczos']

        params += ['-frame-parallel', '1']

        params += [rf'C:\Users\T\Videos\{file.stem}_{crf}_{width}.webm']

        self.exec_ffmpeg(params)

    # @validate_call()
    def h264(
            self,
            file: Path = None,
            width: int = None,
            height: int = None,
            crf: int = 23,
            start_time: str or None = '00:00:00',
            end_time: str or None = None,
            length_time: str or None = None,  # '00:00:00'
            preset: PresetH264 = PresetH264.MEDIUM,
            copy_audio: bool = False,
            copy_video: bool = False,
            tune: TuneH264 = TuneH264.FILM,
            audio_bitrate_kilobit: int = 192,
            fps: int = None,
            first_frame_image: Union[Path, str] = None,
            hardware_encode: bool = False,
            # https://en.wikipedia.org/wiki/Advanced_Video_Coding#Decoded_picture_buffering
            h264_level: str = '3.2'
    ):

        # https://trac.ffmpeg.org/wiki/Encode/H.264

        # https://github.com/rdp/ffmpeg-windows-build-helpers

        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        start = time.monotonic()

        out_file = rf'C:\Users\T\Videos\{file.stem}__{crf}_{width}_{height}-{tune.name}_{hardware_encode}.mp4'
        out_file = Path(out_file)
        out_file_local = Path(self.tmp_dir / 'converted').with_suffix(out_file.suffix)

        if fps is None:
            video_info = self.get_video_media_info(file)
            fps = filter_float(video_info.frame_rate)
            fps = float(fps)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        if length_time:
            params += ['-t', length_time]

        if copy_video:
            params += ['-c:v', 'copy']

        elif hardware_encode:
            # params += ['-c:v', 'h264_amf']
            params += ['-c:v', 'av1_amf']

        else:
            params += ['-c:v', 'libx264']

        """
        film– использовать для качественного киноконтента; снижает деблокировку
        animation– хорош для мультфильмов; использует более высокую деблокировку и больше опорных кадров
        grain– сохраняет зернистую структуру в старом, зернистом пленочном материале
        stillimage– подходит для контента, похожего на слайд-шоу
        fastdecode- позволяет быстрее декодировать, отключив определенные фильтры
        zerolatency– подходит для быстрого кодирования и потоковой передачи с малой задержкой
        """
        if not hardware_encode:
            params += ['-tune', tune.name]
            params += ['-crf', str(crf)]
            params += ['-x264opts', 'opencl']
            params += ['-preset', preset.name]

        #
        # fps_str = ''
        #
        # if fps:
        #     params += ['-r', str(fps)]

        if width:
            params += ['-vf', f'scale={width}:trunc(ow/a/2)*2:flags=lanczos']

        elif height:
            params += ['-vf', f'scale=trunc(ow/a/2)*2:{height}:flags=lanczos']

        if copy_audio:
            params += ['-c:a', 'copy']

        else:
            params += ['-c:a', 'aac']
            params += ['-b:a', f'{audio_bitrate_kilobit}k']

            params += ['-cutoff', '50000']
            params += ['-aac_coder', 'fast']

        params += ['-g', f'{fps * 2}']

        params += ['-level', h264_level]

        # params += ['-filter:v', f'crop=in_w-800:in_h']

        params += ['-pix_fmt', f'yuv420p']

        params += [out_file_local]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        if first_frame_image:
            current_dir = os.getcwd()

            os.chdir(self.tmp_dir)

            try:
                video_info = self.get_video_media_info(out_file_local)

                tmp_mp4 = Path('tmp_preview_video.mp4')

                out_file_with_preview = out_file_local.with_name('video_with_preview.mp4')

                input1 = Path('input1.ts')
                input2 = Path('input2.ts')

                params = []

                params += [self.ffmpeg_file.as_posix() + ' ']
                params += ['-i', first_frame_image]
                params += ['-y']
                params += ['-c:v', 'libx264']
                params += ['-pix_fmt', f'yuv420p']
                params += ['-s', f'{video_info.width}x{video_info.height}']
                params += ['-t', '0.02']
                params += ['-r', video_info.frame_rate]

                params += [tmp_mp4]

                print(params)

                if not self.exec_ffmpeg(params):
                    sound_error()

                    raise ValueError()

                params = []

                params += [self.ffmpeg_file.as_posix() + ' ']
                params += ['-i', tmp_mp4.name]
                params += ['-y']
                params += ['-c', 'copy']
                params += [input1]

                print(params)

                if not self.exec_ffmpeg(params):
                    sound_error()

                    raise ValueError()

                params = []

                params += [self.ffmpeg_file.as_posix() + ' ']
                params += ['-i', out_file_local.name]
                params += ['-y']
                params += ['-c', 'copy']

                params += [input2]

                print(params)

                if not self.exec_ffmpeg(params):
                    sound_error()

                    raise ValueError()

                params = []

                params += [self.ffmpeg_file.as_posix() + ' ']
                params += ['-i', f'concat:{input1.name}|{input2.name}']
                params += ['-y']
                params += ['-c', 'copy']

                params += [out_file_with_preview]

                print(params)

                if not self.exec_ffmpeg(params):
                    sound_error()

                    raise ValueError()

                tmp_mp4.unlink()
                input1.unlink()
                input2.unlink()

                shutil.move(out_file_with_preview, out_file)

            finally:
                os.chdir(current_dir)

        out_file_local.unlink()

        print(f'Ok время {time.monotonic() - start}')

        return out_file

    @validate_call()
    def av1(
            self,
            file: Path = None,
            width: int = None,
            height: int = None,
            crf: int = 23,
            audio_bitrate_kilobit: int = 192,
            fps: int = None,
            lanczos: bool = True
    ):

        # https://trac.ffmpeg.org/wiki/Encode/H.264

        # https://github.com/rdp/ffmpeg-windows-build-helpers

        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        start = time.monotonic()

        out_file = rf'C:\Users\T\Videos\{file.stem}__{crf}_{width}_{height}.mkv'

        out_file = Path(out_file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        params += ['-c:v', 'libsvtav1']

        params += ['-crf', str(crf)]

        if lanczos:
            if width:
                params += ['-vf', f'scale={width}:-1:flags=lanczos']

            elif height:
                params += ['-vf', f'scale={-1}:{height}:flags=lanczos']

        if fps:
            params += ['-filter:v', f'fps={fps}']

        params += ['-c:a', 'aac']
        params += ['-b:a', f'{audio_bitrate_kilobit}k']

        params += ['-pix_fmt', f'yuv420p']

        params += ['-threads', f'12']

        params += ['-preset', f'3']

        params += ['-g', f'300']

        params += ['-cpu-used', f'8']

        params += [out_file]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        print(f'Ok время {time.monotonic() - start}')

        return out_file

    @validate_call()
    def mp3(
            self,
            file: Path = None,
            quality_vbr: int = 1,
            start_time: str = '00:00:00',
            end_time: str = None
    ):
        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        start = time.monotonic()

        out_file = rf'C:\Users\T\Videos\{file.stem}__{quality_vbr}.mp3'

        out_file = Path(out_file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']
        params += ['-vn']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        params += ['-codec:a', 'libmp3lame']

        # params += ['-b:a', f'{audio_bitrate_kilobit}']
        params += ['-qscale:a', f'{quality_vbr}']

        params += ['-compression_level', '0']

        params += ['-cutoff', '48000']

        params += ['-joint_stereo', '0']

        params += [out_file]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        print(f'Ok время {time.monotonic() - start}')

        return self.ConvertResult(in_file=file, out_file=out_file)

    @validate_call()
    def aac(
            self,
            file: Path = None,
            audio_bitrate_kilobit: int = 196,
            start_time: str = '00:00:00',
            end_time: str = None
    ):
        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        start = time.monotonic()

        out_file = rf'C:\Users\T\Videos\{file.stem}__{audio_bitrate_kilobit}.aac'

        out_file = Path(out_file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']
        params += ['-vn']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        params += ['-c:a', 'aac']
        params += ['-b:a', f'{audio_bitrate_kilobit}k']

        params += ['-cutoff', '22000']
        params += ['-aac_coder', 'fast']

        params += [out_file]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        print(f'Ok время {time.monotonic() - start}')

        return self.ConvertResult(in_file=file, out_file=out_file)

    @validate_call()
    def flac(
            self,
            file: Path = None,
            compression_level: int = 12,
            start_time: str = '00:00:00',
            end_time: str = None
    ):
        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        start = time.monotonic()

        out_file = rf'C:\Users\T\Videos\{file.stem}__{compression_level}.flac'

        out_file = Path(out_file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        params += ['-codec:a', 'flac']

        params += ['-compression_level', f'{compression_level}']

        # params += ['-prediction_order_method', '8level']

        # params += ['--embed-chapters']
        # params += ['--yes-playlist']
        # params += ['--embed-subs']
        # params += ['--sub-langs', 'ru,en,ua,ja']
        # params += ['--write-auto-subs']
        # params += ['--force-overwrites']

        params += [out_file]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        print(f'Ok время {time.monotonic() - start}')

        return self.ConvertResult(in_file=file, out_file=out_file)

    def add_video_preview(self, file: Union[Path, str], image: Union[Path, str], width: int, height: int, fps: int, ):

        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')

        if not image:
            image = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')

        file = Path(file)

        image = Path(image)

        params = []

        params += [r'../ffmpeg/bin/ffmpeg.exe ']
        # params += ['-i', file]
        params += ['-i', image]
        params += ['-y']

        params += ['-c:v', 'libx264']
        params += ['-map', '0']
        params += ['-c', 'copy']
        params += ['-disposition:0', 'attached_pic']
        out_file = file.with_stem('with_preview')

        params += [out_file]

        if not self.exec_ffmpeg(params):
            sound_error()
            raise ValueError()

        if not out_file.is_file():
            sound_error()
            raise ValueError('Вставка превью, ошибка')

        return out_file

    @validate_call()
    def extract_screenshot_from_video(self, out_file_image: Path, file: Path = None, start_time: str = '00:00:00', ):

        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        params += ['-ss', start_time]
        params += ['-frames:v', '1']
        # params += ['-update', 'true']

        out_file = out_file_image.with_suffix('.png')

        if out_file.is_file():
            out_file_image.unlink()

        params += [out_file]

        if not self.exec_ffmpeg(params):
            sound_error()
            raise ValueError()

        if not out_file.is_file():
            sound_error()

            raise ValueError('Ошибка получения превью')

        return out_file

    @validate_call()
    def to_size(
            self,
            max_size_bytes: int,
            crf=23,
            test_original=False,
            start_time='00:00:00',
            end_time=None,
            start_height=50,
            preset: PresetH264 = PresetH264.MEDIUM,
            tune: TuneH264 = TuneH264.FILM,
            fps: int = None
    ):

        cache_item = self.cache.get('to_size_file_path')

        if not cache_item:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')

        else:
            file = fd.askopenfilename(initialdir=cache_item)

        file = Path(file)

        self.cache.set('to_size_file_path', file.parent.as_posix())

        if test_original:
            out_file = self.h264(file=file, crf=crf, start_time=start_time, end_time=end_time, preset=preset, tune=tune, fps=fps)

            if out_file.stat().st_size < max_size_bytes:
                return True

        res = []

        height_inc = 8

        last_size_file = 0

        for i in range(0, 1000):

            height = start_height + i * height_inc

            print(f'Высота {height}')

            out_file = self.h264(file=file, height=height, crf=crf, start_time=start_time, end_time=end_time, preset=preset, tune=tune, fps=fps)

            if out_file.stat().st_size > 0:
                last_size_file = out_file.stat().st_size

            size_file = out_file.stat().st_size

            if max_size_bytes < size_file or height > 1280:
                out_file.unlink()

                break

            else:
                res.append(dict(out_file=out_file, size_file=size_file))

        if not res:
            sound_error()
            raise ValueError('С первой попытки файл слишком большой')

        sort = sorted(res, key=itemgetter('size_file'))
        sort.pop()

        for item in sort:
            if item['out_file'].is_file():
                item['out_file'].unlink()

        return True

    @validate_call()
    def delogo(
            self,
            x: int,
            y: int,
            width: int,
            height: int,
            show_green_marker: Literal[0, 1],
            file: Path = None,
            start_time: str = '00:00:00',
            end_time: str = None,

    ):
        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        start = time.monotonic()

        out_file = rf'C:\Users\T\Videos\{file.stem}.mkv'

        out_file = Path(out_file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        params += ['-c:v', 'ffv1']

        params += ['-codec:a', 'flac']

        params += ['-vf', f'delogo=x={x}:y={y}:w={width}:h={height}:show={show_green_marker}']

        params += ['-threads', '12']

        params += [out_file]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        print(f'Ok время {time.monotonic() - start}')

        return self.ConvertResult(in_file=file, out_file=out_file)

    def get_video_media_info(self, file: Union[Path, str]):

        media_info = MediaInfo.parse(filename=file)

        track_video = next(i for i in media_info.tracks if i.track_type.casefold() == 'Video'.casefold())

        return track_video

    @validate_call()
    def mkv_h264_pcm(
            self,
            file: Path = None,
            width: int = None,
            height: int = None,
            crf: int = 23,
            start_time: str or None = '00:00:00',
            end_time: str or None = None,
            length_time: str or None = None,  # '00:00:00'
            preset: PresetH264 = PresetH264.MEDIUM,
            tune: TuneH264 = TuneH264.FILM,
    ):

        # https://trac.ffmpeg.org/wiki/Encode/H.264

        # https://github.com/rdp/ffmpeg-windows-build-helpers

        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        out_file = rf'C:\Users\T\Videos\{file.stem}__{crf}_{width}_{height}-{tune.name}.mkv'

        out_file = Path(out_file)

        out_file_local = Path(self.tmp_dir / 'converted').with_suffix(out_file.suffix)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        if length_time:
            params += ['-t', length_time]

        params += ['-c:v', 'libx264']

        params += ['-tune', tune.name]

        params += ['-crf', str(crf)]
        params += ['-preset', preset.name]

        if width:
            params += ['-vf', f'scale={width}:-1:flags=lanczos']

        elif height:
            params += ['-vf', f'scale={-1}:{height}:flags=lanczos']
        #
        # if fps:
        #     params += ['-filter:v', f'fps={fps}']

        info = self.get_video_media_info(out_file)

        params += ['-c:a', 'flac']
        params += ['-x264opts', 'opencl']
        params += ['-g', str(filter_float(info.frame_rate))]
        params += ['-level', '3.1']
        params += ['-pix_fmt', f'yuv420p']

        params += [out_file_local]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        shutil.move(out_file_local, out_file)

    @validate_call()
    def vorbis(
            self,
            file: Path = None,
            quality_vbr: int = 10,
            # audio_bitrate_kilobit: int = 192,

            start_time: str = '00:00:00',
            end_time: str = None
    ):
        if not file:
            file = fd.askopenfilename(initialdir='c:/ProjectsMy/youtube/download')
            file = Path(file)

        start = time.monotonic()

        out_file = rf'C:\Users\T\Videos\{file.stem}__{quality_vbr}.ogg'

        out_file = Path(out_file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        params += ['-codec:a', 'libvorbis']

        params += ['-q:a', f'{quality_vbr}']
        params += ['-vn']

        params += [out_file]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        print(f'Ok время {time.monotonic() - start}')

        return self.ConvertResult(in_file=file, out_file=out_file)


class Youtube:
    def __init__(
            self,
            cookies_from_browser: str = None,
            proxy: str = None,
    ):

        self.cookies_from_browser = cookies_from_browser
        self.proxy = proxy

        self.file_name_format = '"../download/%(title)s -- %(uploader)s -- %(webpage_url)s -- %(upload_date)s.%(ext)s"'
        self.file_name_format_audio = '"../download/%(title)s -- %(uploader)s -- %(webpage_url)s -- %(upload_date)s audio.%(ext)s"'

        self.yt_dlp_file = Path('./yt-dlp.exe')

        self.tkinter_root = Tk()

        self.converter_obj = Converter()

        self.root = self.tkinter_root

        self.root.geometry('500x750')

        self.root.resizable(False, False)

        self.root.title = 'Выбор'

        self.script_dir = Path(__file__).parent

        self.tmp_dir = self.script_dir / 'tmp'

        self.cache = diskcache.Cache((self.tmp_dir / 'youtube_cache').as_posix())

        # label = ttk.Label(text=self.root.clipboard_get())
        # label.pack(fill='x', padx=5, pady=pady)

        padx = 3
        pady = 3

        selected_size = tkinter.StringVar(value='480')
        sizes = (
            ('Высота 1080', 1080),
            ('Высота 720', 720),
            ('Высота 480', 480),
            ('Высота 360', 360),
            ('Высота 240', 240),
            ('Высота 144', 144),
            ('Высота не указывать', 1),
            ('Создать ссылку', 3),
        )

        for size in sizes:
            r = ttk.Radiobutton(
                self.root,
                text=size[0],
                value=size[1],
                variable=selected_size
            )
            r.pack(fill='x', padx=padx, pady=pady)

        # convert_to_mp4 = tkinter.BooleanVar(value=False)
        # checkbox_mp4 = ttk.Checkbutton(text='В mp4', variable=convert_to_mp4, onvalue=True, offvalue=False)
        # checkbox_mp4.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Скачать ютуб",
            command=lambda: self.exec_button(size_video=selected_size),

        )

        button.pack(fill='x', padx=padx, pady=pady)

        self.button_download_audio = ttk.Button(
            self.root,
            text="Скачать ютуб аудио ",
            command=lambda: self.download_audio()

        )

        self.button_download_audio.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Скачать ролик с любого хостнга",
            command=lambda: self.download_any(),

        )

        button.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Конвертация Телеграм",
            command=lambda: self.convert_to_telegram(
                tune=tune.get(),
                height=selected_size.get(),
                start_time=self.edit_start_video_time.get(),
                end_time=self.edit_end_video_time.get()
            )
        )

        button.pack(fill='x', padx=padx, pady=pady)

        self.label1 = ttk.Label(self.root, text='Время для превью')
        self.label1.pack(fill='x', padx=padx, pady=pady)

        self.preview_time = ttk.Entry(self.root)
        self.preview_time.insert(0, '00:00:05')
        self.preview_time.pack(fill='x', padx=padx, pady=pady)

        self.label2 = ttk.Label(self.root, text='Начало видео')
        self.label2.pack(fill='x', padx=padx, pady=pady)

        self.edit_start_video_time = ttk.Entry(self.root)
        self.edit_start_video_time.insert(0, '00:00:00')
        self.edit_start_video_time.pack(fill='x', padx=padx, pady=pady)

        self.label3 = ttk.Label(self.root, text='Конец видео')
        self.label3.pack(fill='x', padx=padx, pady=pady)

        self.edit_end_video_time = ttk.Entry(self.root)
        self.edit_end_video_time.insert(0, '08:00:00')
        self.edit_end_video_time.pack(fill='x', padx=padx, pady=pady)

        tune = ttk.Combobox(self.root, values=list(i.name for i in TuneH264))

        tune.current(0)

        tune.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Конвертация быстро",
            command=self.convert_fast
        )

        button.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Конвертация Vorbis",
            command=lambda: self.convert_to_vorbis()
        )

        button.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Конвертация FLAC",
            command=lambda: self.convert_to_flac()
        )

        button.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Конвертация MP3",
            command=lambda: self.convert_to_mp3()
        )

        button.pack(fill='x', padx=padx, pady=pady)

        button = ttk.Button(
            self.root,
            text="Обновить yt-dlp",
            command=lambda: self.update_yt_dlp()
        )

        button.pack(fill='x', padx=padx, pady=pady)

        self.label_status = ttk.Label(self.root, text="")
        self.label_status.pack(fill='x', padx=padx, pady=pady)

        self.status = None

        self.root.mainloop()

    @validate_call()
    def download_archive(
            self, height: int = 720,
            convert_to_mp4: bool = False,
    ):

        # https://github.com/yt-dlp/yt-dlp

        url = self.tkinter_root.clipboard_get()

        self.status = f'Старт скачивания {url}'

        if not isinstance(url, str) or not re.match(r'^http', url):
            self.sound_error()

            raise ValueError('Неправильный url')

        params = []

        params += [self.yt_dlp_file, url]

        params += ['--ffmpeg-location', '../ffmpeg/bin']

        params += ['--embed-chapters']
        params += ['--yes-playlist']
        # params += ['--embed-subs']
        # params += ['--sub-langs', 'ru,en,ua,ja']
        # params += ['--write-auto-subs']
        params += ['--force-overwrites']

        if convert_to_mp4:
            params += ['--recode-video', 'mp4']

        params += ['-f', f'bestvideo[height<={height}]+bestaudio']
        params += ['-o', self.file_name_format]

        if self.cookies_from_browser:
            params += ['--cookies-from-browser', self.cookies_from_browser]

        if self.cookies_from_browser:
            params += ['--proxy', self.proxy]

        if not self.converter_obj.exec_ffmpeg(params):

            self.sound_error()

            raise ValueError('Ошибка скачивания')

        self.status = 'Ок'

    def update_yt_dlp(self):
        if not self.yt_dlp_file.is_file():
            url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
            output_path = "yt-dlp.exe"

            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            print(f"Файл сохранён как {output_path}")

        else:
            params = []

            params += [self.yt_dlp_file, '-U']

            self.converter_obj.exec_ffmpeg(params)

    def create_link(self):
        initial_dir = Path('c:/ProjectsMy/youtube/download')

        len_initial_dir_parts = len(initial_dir.parts)

        if source := fd.askopenfilename(initialdir=initial_dir, title='Источник для ссылки'):

            source = Path(source)

            # source = Path(*source.parts[len_initial_dir_parts:])

            if target := fd.askdirectory(initialdir='c:/ProjectsMy/youtube/download', title='В какую папку ссылка'):

                target = Path(target)

                target_file = target / source.name

                # target_file = Path('./') / Path(*target_file.parts[len_initial_dir_parts:])

                target_file.symlink_to(target=source)

        pass

    def exec_button(self, size_video, convert_to_mp4: bool = False):

        self.status = 'Статус'

        size_video_var = size_video.get()

        if size_video_var == '720':
            self.download_archive(height=720, convert_to_mp4=convert_to_mp4)

        elif size_video_var == '144':
            self.download_archive(height=144, convert_to_mp4=convert_to_mp4)

        elif size_video_var == '480':
            self.download_archive(height=480, convert_to_mp4=convert_to_mp4)

        elif size_video_var == '240':
            self.download_archive(height=240, convert_to_mp4=convert_to_mp4)

        elif size_video_var == '360':
            self.download_archive(height=360, convert_to_mp4=convert_to_mp4)

        elif size_video_var == '1080':
            self.download_archive(height=1080, convert_to_mp4=convert_to_mp4)

        elif size_video_var == '3':
            self.create_link()

        elif size_video_var == '1':
            self.download_archive(height=1080, convert_to_mp4=convert_to_mp4)

        else:
            self.sound_error()

            raise ValueError('Не найдено значение для меню')

        # self.download_audio()

        sound_ok()

        self.status = 'Ок'

    @validate_call()
    def download_any(self):

        url = self.tkinter_root.clipboard_get()

        self.status = f'Старт скачивания {url}'

        if not isinstance(url, str) or not re.match(r'^http', url):
            self.sound_error()

            raise ValueError('Неправильный url')

        params = []

        params += [self.yt_dlp_file, url]

        # params += ['--ffmpeg-location', '../ffmpeg/bin']
        #
        # params += ['--embed-chapters']
        # params += ['--yes-playlist']
        # params += ['--embed-subs']
        # params += ['--sub-langs', 'ru,en,ua,ja']
        # params += ['--write-auto-subs']
        params += ['--force-overwrites']

        params += ['-f', f'best']

        params += ['-o', self.file_name_format]

        if not self.converter_obj.exec_ffmpeg(params):
            self.sound_error()

            raise ValueError('Ошибка скачивания')

        self.status = 'Ок'

        sound_ok()

    def convert_to_telegram(self, tune: str, height: Union[int, str] = None, start_time: str = '00:00:00', end_time: str = None):

        file = self.open_file_with_cache(start_dir='c:/ProjectsMy/youtube/download', cache_key='convert_to_telegram')

        if file.as_posix() == '.':
            self.sound_error()

            return

        preview = self.open_file_with_cache(start_dir='c:/ProjectsMy/youtube/download', cache_key='convert_to_telegram_preview')

        if preview.as_posix() == '.':
            preview = self.converter_obj.extract_screenshot_from_video(
                out_file_image=Path(rf'C:\Users\T\Videos\screenshot.png'),
                file=file,
                start_time=self.preview_time.get()
            )

        height = int(height)

        width = None

        if height:
            if height == 144:
                width = 256

            elif height == 240:
                width = 426

            elif height == 360:
                width = 640

            elif height == 480:
                width = 854

            elif height == 720:
                width = 1280

            elif height == 1080:
                width = 1920

        track_video = self.converter_obj.get_video_media_info(file=file)

        preset = PresetH264.VERYSLOW
        tune = TuneH264(TuneH264[tune])
        audio_bitrate_kilobit = 256
        crf = 23

        if width is None:
            out_video = self.converter_obj.h264(
                crf=crf,
                preset=preset,
                tune=tune,
                audio_bitrate_kilobit=audio_bitrate_kilobit,
                file=file,
                first_frame_image=preview,
                start_time=start_time,
                end_time=end_time
            )

        else:
            if width >= track_video.width:
                out_video = self.converter_obj.h264(
                    crf=crf,
                    preset=preset,
                    tune=tune,
                    audio_bitrate_kilobit=audio_bitrate_kilobit,
                    file=file,
                    first_frame_image=preview,
                    start_time=start_time,
                    end_time=end_time
                )

            else:
                out_video = self.converter_obj.h264(
                    crf=crf,
                    width=width,
                    preset=preset,
                    tune=tune,
                    audio_bitrate_kilobit=audio_bitrate_kilobit,
                    file=file,
                    first_frame_image=preview,
                    start_time=start_time,
                    end_time=end_time
                )

        sound_ok()

    def convert_fast(self):
        # self.converter_obj.to_size(
        #     max_size_bytes=25000000000000 * 1024 * 1024,
        #     crf=23,
        #     # start_time='02:20:00',
        #     # end_time='02:30:00',
        #     test_original=False,
        #     start_height=1080,
        #     fps=30,
        #     preset=self.converter_obj.PresetH264.ultrafast,
        #     tune=self.converter_obj.TuneH264.film,
        # )
        #
        # self.converter_obj.av1(
        #     crf=63,
        #     height=480
        #
        # )
        self.converter_obj.mkv_h264_pcm(
            crf=23,
            # start_time='02:20:00',
            # end_time='02:30:00',
            # height=144,
            # fps=30,
            preset=PresetH264.ULTRAFAST,
            tune=TuneH264.FILM,
            # copy_audio=True,
            # copy_video=True

        )

        sound_ok()

    def convert_to_mp3(self):
        self.status = 'Статус'

        file = self.open_file_with_cache(start_dir='c:/ProjectsMy/youtube/download', cache_key='convert_to_mp3')

        res = self.converter_obj.mp3(file=file, start_time='00:00:00')

        self.converter_obj.extract_screenshot_from_video(
            file=res.in_file,
            out_file_image=Path(r'C:\Users\T\Videos\screenshot.png'),
            start_time='00:00:03'
        )

        sound_ok()

        self.status = 'Ок'

    def convert_to_vorbis(self):
        self.status = 'Статус'

        file = self.open_file_with_cache(start_dir='c:/ProjectsMy/youtube/download', cache_key='convert_to_vorbis')

        res = self.converter_obj.vorbis(file=file, quality_vbr=7, start_time='00:00:00')

        self.converter_obj.extract_screenshot_from_video(
            file=res.in_file,
            out_file_image=Path(r'C:\Users\T\Videos\screenshot.png'),
            start_time=self.preview_time.get()
        )

        sound_ok()

        self.status = 'Ок'

    def convert_to_flac(self):
        self.status = 'Статус'

        res = self.converter_obj.flac(compression_level=12, start_time='00:00:00')

        self.converter_obj.extract_screenshot_from_video(
            file=res.in_file,
            out_file_image=Path(r'C:\Users\T\Videos\screenshot.png'),
            start_time='00:00:03'
        )

        self.status = 'Ок'

        sound_ok()

    def convert_to_aac(self):
        self.status = 'Статус'

        file = self.open_file_with_cache(start_dir='c:/ProjectsMy/youtube/download', cache_key='convert_to_mp3')

        res = self.converter_obj.aac(file=file, start_time='00:00:00')

        self.converter_obj.extract_screenshot_from_video(
            file=res.in_file,
            out_file_image=Path(r'C:\Users\T\Videos\screenshot.png'),
            start_time='00:00:03'
        )

        sound_ok()

        self.status = 'Ок'

    def open_file_with_cache(self, start_dir: Union[Path, str], cache_key: str):

        start_dir = Path(start_dir)

        cache_item = self.cache.get(cache_key)

        if not cache_item:
            file = fd.askopenfilename(initialdir=start_dir)

        else:
            file_path = Path(cache_item)

            if file_path.is_file():
                file = fd.askopenfilename(initialfile=file_path, initialdir=file_path.parent)

            else:
                file = fd.askopenfilename(initialdir=file_path)

        file = Path(file)

        if file.is_file():
            self.cache.set(cache_key, file.as_posix())

        return file

    @validate_call()
    def download_audio(self):
        self.status = 'Старт'

        url = self.tkinter_root.clipboard_get()

        if not isinstance(url, str) or not re.match(r'^http', url):
            self.sound_error()

            raise ValueError('Неправильный url')

        params = []

        params += [self.yt_dlp_file, url]

        params += ['--ffmpeg-location', '../ffmpeg/bin']

        params += ['--extract-audio']
        params += ['--force-overwrites']
        # params += ['--audio-format', 'flac']
        params += ['--embed-chapters']
        params += ['--yes-playlist']
        params += ['--embed-subs']
        params += ['--sub-langs', 'ru,en,ua,ja']
        params += ['--write-auto-subs']

        params += ['-f', f'bestaudio']
        params += ['-o', self.file_name_format_audio]

        if not self.converter_obj.exec_ffmpeg(params):
            self.sound_error()

            self.status = 'Ошибка'

        self.status = 'Ок'

    def sound_error(self):
        self.status = 'Ошибка'

        winsound.Beep(500, 300)
        time.sleep(0.05)

        winsound.Beep(500, 300)

    @property
    def status(self):
        return None

    @status.setter
    def status(self, status):
        self.label_status.config(text=status)

        self.label_status.update_idletasks()


def sound_error():

    winsound.Beep(500, 300)
    time.sleep(0.05)

    winsound.Beep(500, 300)


def sound_ok():
    winsound.Beep(500, 300)


def filter_float(value: str):
    value2 = str(value).replace(',', '.')

    value3 = float(value2)

    return value3


youtube = Youtube(cookies_from_browser='firefox:24x3vwfc.tmp', proxy='socks5://192.168.2.87:38018')
