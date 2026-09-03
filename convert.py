import dataclasses
import enum
import queue
import re
import shutil
import subprocess
import threading
from operator import itemgetter

from pathlib import Path
from typing import Literal

import winsound

from tkinter import filedialog as fd

import time

import urllib.error
import urllib.request

from pydantic import validate_call

from tkinter import Tk, ttk, messagebox

import tkinter

import diskcache

from pymediainfo import MediaInfo


YT_DLP_DOWNLOAD_URL: str = 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe'

FFMPEG_SEARCH_PATHS: tuple[Path, ...] = (
    Path(r'C:\Users\work-\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe'),
    Path(r'C:\ProgramData\chocolatey\lib\ffmpeg-full\tools\ffmpeg\bin\ffmpeg.exe'),
    Path(r'C:\ProgramData\chocolatey\bin\ffmpeg.exe'),
    Path(r'C:\ffmpeg\bin\ffmpeg.exe'),
)

# Приоритет: NVIDIA -> Intel -> AMD. Каждый шаблон флагов проверяется тестовым
# кодированием целиком (не только наличие энкодера в списке ffmpeg -encoders),
# чтобы отсеять энкодеры, которые формально есть, но не инициализируются на
# данном железе/драйвере.
GPU_H264_ENCODERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('h264_nvenc', ('-rc', 'constqp', '-qp', '{crf}')),
    ('h264_qsv', ('-global_quality', '{crf}')),
    ('h264_amf', ('-quality', 'quality', '-rc', 'cqp', '-qp_i', '{crf}', '-qp_p', '{crf}')),
)

VIDEOS_OUTPUT_DIR: Path = Path('data') / 'video'

TEMP_DIR: Path = Path('data') / 'tmp'
TEMP_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOAD_DIR: Path = Path('data') / 'download'
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR: Path = Path('data') / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def log_conversion(line: str) -> None:
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    with open(LOGS_DIR / 'conversion.log', 'a', encoding='utf-8') as log_file:
        log_file.write(f'{timestamp} {line}\n')


class Converter:

    def __init__(self) -> None:

        self.cache = diskcache.Cache('diskcache')

        self.ffmpeg_file = self.find_ffmpeg()

    @staticmethod
    def find_ffmpeg() -> Path:

        for candidate_path in FFMPEG_SEARCH_PATHS:
            if candidate_path.is_file():
                return candidate_path

        found_in_path = shutil.which('ffmpeg')

        if found_in_path:
            ffmpeg_path = Path(found_in_path)

            return ffmpeg_path

        raise FileNotFoundError(f'ffmpeg не найден. Проверь FFMPEG_SEARCH_PATHS или PATH: {FFMPEG_SEARCH_PATHS}')

    def detect_gpu_h264_encoder(self) -> tuple[str, tuple[str, ...]] | None:

        if hasattr(self, '_gpu_h264_encoder_cache'):
            return self._gpu_h264_encoder_cache

        for encoder_name, extra_args_template in GPU_H264_ENCODERS:
            extra_args = [arg.format(crf=23) for arg in extra_args_template]

            works = self.exec_ffmpeg(
                [
                    self.ffmpeg_file.as_posix() + ' ',
                    '-hide_banner',
                    '-loglevel', 'error',
                    '-f', 'lavfi',
                    '-i', 'testsrc=duration=0.5:size=320x240:rate=10',
                    '-frames:v', '5',
                    '-c:v', encoder_name,
                    *extra_args,
                    '-pix_fmt', 'yuv420p',
                    '-f', 'null', '-',
                ]
            )

            if works:
                self._gpu_h264_encoder_cache = (encoder_name, extra_args_template)

                return self._gpu_h264_encoder_cache

        self._gpu_h264_encoder_cache = None

        return None

    class TuneH264(enum.Enum):
        film = 0
        animation = 1
        grain = 2
        stillimage = 3
        fastdecode = 4
        zerolatency = 5

    class PresetH264(enum.Enum):
        ultrafast = enum.auto()
        superfast = enum.auto()
        veryfast = enum.auto()
        faster = enum.auto()
        fast = enum.auto()
        medium = enum.auto()
        slow = enum.auto()
        slower = enum.auto()
        veryslow = enum.auto()
        placebo = enum.auto()

    @dataclasses.dataclass
    class ConvertResult:
        in_file: Path
        out_file: Path

    @staticmethod
    @validate_call
    def exec_ffmpeg(args: list):
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, shell=False)

        (out, err) = proc.communicate()

        if out is not None:
            print(out.decode('utf-8', errors='replace'))

        return proc.returncode == 0

    @staticmethod
    def exec_with_progress(args: list, on_line=None):
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
        )

        for line in proc.stdout:
            line = line.strip('\r\n')

            print(line)

            if on_line and line:
                on_line(line)

        proc.wait()

        return proc.returncode == 0

    @validate_call
    def vp9(self, file: Path | None = None, width: int | None = None, crf: int = 23, vorbis_quality: int = 7):

        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
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

        params += [VIDEOS_OUTPUT_DIR / f'{file.stem}_{crf}_{width}.webm']

        self.exec_ffmpeg(params)

    @validate_call
    def h264(
            self,
            file: Path | None = None,
            width: int | None = None,
            height: int | None = None,
            crf: int = 23,
            start_time: str | None = '00:00:00',
            end_time: str | None = None,
            length_time: str | None = None,  # '00:00:00'
            preset: PresetH264 = PresetH264.medium,
            copy_audio: bool = False,
            copy_video: bool = False,
            tune: TuneH264 = TuneH264.film,
            audio_bitrate_kilobit: int = 192,
            fps: int | None = None,
            first_frame_image: Path | str | None = None
    ):

        # https://trac.ffmpeg.org/wiki/Encode/H.264

        # https://github.com/rdp/ffmpeg-windows-build-helpers

        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        start = time.monotonic()

        out_file = VIDEOS_OUTPUT_DIR / f'{file.stem}__{crf}_{width}_{height}-{tune.name}.mp4'
        out_file_local = (TEMP_DIR / 'converted').with_suffix(out_file.suffix)

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
        params += ['-tune', tune.name]

        params += ['-crf', str(crf)]
        params += ['-preset', preset.name]
        #
        # fps_str = ''
        #
        # if fps:
        #     params += ['-r', str(fps)]

        if width:
            params += ['-vf', f'scale={width}:-1:flags=lanczos']

        elif height:
            params += ['-vf', f'scale={-1}:{height}:flags=lanczos']

        if copy_audio:
            params += ['-c:a', 'copy']

        else:
            params += ['-c:a', 'aac']
            params += ['-b:a', f'{audio_bitrate_kilobit}k']

            params += ['-cutoff', '22000']
            params += ['-aac_coder', 'fast']

        params += ['-x264opts', 'opencl']
        params += ['-g', f'{fps * 2}']
        params += ['-level', '3.0']

        # params += ['-filter:v', f'crop=in_w-800:in_h']

        params += ['-pix_fmt', f'yuv420p']

        params += [out_file_local]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        if first_frame_image:

            video_info = self.get_video_media_info(out_file_local)

            tmp_mp4 = TEMP_DIR / 'tmp_preview_video.mp4'

            out_file_with_preview = out_file_local.with_name('video_with_preview.mp4')

            input1 = TEMP_DIR / 'input1.ts'
            input2 = TEMP_DIR / 'input2.ts'

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
            params += ['-i', tmp_mp4]
            params += ['-y']
            params += ['-c', 'copy']
            params += [input1]

            print(params)

            if not self.exec_ffmpeg(params):
                sound_error()

                raise ValueError()

            params = []

            params += [self.ffmpeg_file.as_posix() + ' ']
            params += ['-i', out_file_local]
            params += ['-y']
            params += ['-c', 'copy']

            params += [input2]

            print(params)

            if not self.exec_ffmpeg(params):
                sound_error()

                raise ValueError()

            params = []

            params += [self.ffmpeg_file.as_posix() + ' ']
            params += ['-i', f'concat:{input1.as_posix()}|{input2.as_posix()}']
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

        out_file_local.unlink()

        print(f'Ok время {time.monotonic() - start}')

        return out_file

    @validate_call
    def av1(
            self,
            file: Path | None = None,
            width: int | None = None,
            height: int | None = None,
            crf: int = 23,
            audio_bitrate_kilobit: int = 192,
            fps: int | None = None,
            lanczos: bool = True
    ):

        # https://trac.ffmpeg.org/wiki/Encode/H.264

        # https://github.com/rdp/ffmpeg-windows-build-helpers

        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        start = time.monotonic()

        out_file = VIDEOS_OUTPUT_DIR / f'{file.stem}__{crf}_{width}_{height}.mkv'

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

    @validate_call
    def mp3(
            self,
            file: Path | None = None,
            quality_vbr: int = 1,
            # audio_bitrate_kilobit: int = 192,

            start_time: str = '00:00:00',
            end_time: str | None = None
    ):
        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        start = time.monotonic()

        out_file = VIDEOS_OUTPUT_DIR / f'{file.stem}__{quality_vbr}.mp3'

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        if start_time:
            params += ['-ss', start_time]

        if end_time:
            params += ['-to', end_time]

        params += ['-codec:a', 'libmp3lame']

        params += ['-q:a', f'{quality_vbr}']

        params += ['-joint_stereo', '0']

        params += [out_file]

        print(params)

        if not self.exec_ffmpeg(params):
            sound_error()

            raise ValueError()

        print(f'Ok время {time.monotonic() - start}')

        return self.ConvertResult(in_file=file, out_file=out_file)

    @validate_call
    def flac(
            self,
            file: Path | None = None,
            compression_level: int = 12,
            start_time: str = '00:00:00',
            end_time: str | None = None
    ):
        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        start = time.monotonic()

        out_file = VIDEOS_OUTPUT_DIR / f'{file.stem}__{compression_level}.flac'

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

    def add_video_preview(self, file: Path | str, image: Path | str, width: int, height: int, fps: int, ):

        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())

        if not image:
            image = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())

        file = Path(file)

        image = Path(image)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
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

    @validate_call
    def extract_screenshot_from_video(self, out_file_image: Path, file: Path | None = None, start_time: str = '00:00:00', ):

        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        params = []

        params += [self.ffmpeg_file.as_posix() + ' ']
        params += ['-i', file]
        params += ['-y']

        params += ['-ss', start_time]
        params += ['-frames:v', '1']
        params += ['-update', '1']

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

    @validate_call
    def to_size(
            self,
            max_size_bytes: int,
            crf=23,
            test_original=False,
            start_time='00:00:00',
            end_time=None,
            start_height=50,
            preset: PresetH264 = PresetH264.medium,
            tune: TuneH264 = TuneH264.film,
            fps: int | None = None
    ):

        cache_item = self.cache.get('to_size_file_path')

        if not cache_item:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())

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

    @validate_call
    def delogo(
            self,
            x: int,
            y: int,
            width: int,
            height: int,
            show_green_marker: Literal[0, 1],
            file: Path | None = None,
            start_time: str = '00:00:00',
            end_time: str | None = None,

    ):
        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        start = time.monotonic()

        out_file = VIDEOS_OUTPUT_DIR / f'{file.stem}.mkv'

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

    def get_video_media_info(self, file: Path | str):

        media_info = MediaInfo.parse(filename=file)

        track_video = next(i for i in media_info.tracks if i.track_type.casefold() == 'Video'.casefold())

        return track_video

    @validate_call
    def mkv_h264_pcm(
            self,
            file: Path | None = None,
            width: int | None = None,
            height: int | None = None,
            crf: int = 23,
            start_time: str | None = '00:00:00',
            end_time: str | None = None,
            length_time: str | None = None,  # '00:00:00'
            preset: PresetH264 = PresetH264.medium,
            copy_audio: bool = False,
            copy_video: bool = False,
            tune: TuneH264 = TuneH264.film,
            fps: int | None = None,
            use_gpu: bool = False,
    ):

        # https://trac.ffmpeg.org/wiki/Encode/H.264

        # https://github.com/rdp/ffmpeg-windows-build-helpers

        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        out_file = VIDEOS_OUTPUT_DIR / f'{file.stem}_fast.mkv'

        out_file_local = (TEMP_DIR / 'converted').with_suffix(out_file.suffix)

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

        gpu_encoder = self.detect_gpu_h264_encoder() if use_gpu else None

        if gpu_encoder:
            encoder_name, extra_args_template = gpu_encoder

            params += ['-c:v', encoder_name]
            params += [arg.format(crf=crf) for arg in extra_args_template]

        else:
            params += ['-c:v', 'libx264']

            params += ['-tune', tune.name]

            params += ['-crf', str(crf)]
            params += ['-preset', preset.name]

        if width:
            params += ['-vf', f'scale={width}:-1:flags=lanczos']

        elif height:
            params += ['-vf', f'scale={-1}:{height}:flags=lanczos']

        if fps:
            params += ['-filter:v', f'fps={fps}']

        info = self.get_video_media_info(file)

        params += ['-c:a', 'libmp3lame']
        params += ['-q:a', '4']

        if not gpu_encoder:
            params += ['-x264opts', 'opencl']

        params += ['-g', str(filter_float(info.frame_rate))]
        params += ['-level', '3.1']
        params += ['-pix_fmt', f'yuv420p']

        params += [out_file_local]

        print(params)

        encoder_used = gpu_encoder[0] if gpu_encoder else 'libx264'

        start = time.monotonic()

        success = self.exec_ffmpeg(params)

        elapsed = time.monotonic() - start

        if not success:
            log_conversion(f'FAIL file={file.name} encoder={encoder_used} crf={crf} elapsed={elapsed:.1f}s')

            sound_error()

            raise ValueError()

        shutil.move(out_file_local, out_file)

        log_conversion(
            f'OK file={file.name} encoder={encoder_used} crf={crf} elapsed={elapsed:.1f}s out={out_file.name}'
        )

    @validate_call
    def vorbis(
            self,
            file: Path | None = None,
            quality_vbr: int = 10,
            # audio_bitrate_kilobit: int = 192,

            start_time: str = '00:00:00',
            end_time: str | None = None
    ):
        if not file:
            file = fd.askopenfilename(initialdir=DOWNLOAD_DIR.as_posix())
            file = Path(file)

        start = time.monotonic()

        out_file = VIDEOS_OUTPUT_DIR / f'{file.stem}__{quality_vbr}.ogg'

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
    def __init__(self):
        self.file_name_format = f'{DOWNLOAD_DIR.as_posix()}/%(title)s -- %(uploader)s -- %(webpage_url)s -- %(upload_date)s.%(ext)s'
        self.file_name_format_audio = f'{DOWNLOAD_DIR.as_posix()}/%(title)s -- %(uploader)s -- %(webpage_url)s -- %(upload_date)s audio.%(ext)s'

        self.yt_dlp_file = Path('./yt-dlp.exe')

        self.tkinter_root = Tk()

        self.converter_obj = Converter()

        self.root = self.tkinter_root

        window_width = 500
        window_height = 750

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        position_x = (screen_width - window_width) // 2
        position_y = (screen_height - window_height) // 2

        self.root.geometry(f'{window_width}x{window_height}+{position_x}+{position_y}')

        self.root.resizable(False, False)

        self.root.title = 'Выбор'

        self.cache = diskcache.Cache('diskcache')

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
            command=lambda: self.download_any(height=selected_size.get()),

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

        tune = ttk.Combobox(self.root, values=list(i.name for i in self.converter_obj.TuneH264))

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
            text="Обновить yt-dlp",
            command=lambda: self.update_yt_dlp()
        )

        button.pack(fill='x', padx=padx, pady=pady)

        self.label_status = ttk.Label(self.root, text="")
        self.label_status.pack(fill='x', padx=padx, pady=pady)

        self.status = None

        self._status_queue = queue.Queue()

        self.root.after(100, self._poll_status_queue)

        self.root.mainloop()

    def _poll_status_queue(self) -> None:
        try:
            while True:
                kind, payload = self._status_queue.get_nowait()

                if kind == 'status':
                    self.label_status.config(text=payload)

                elif kind == 'done':
                    ok, error_message = payload

                    if ok:
                        self.label_status.config(text='Ок')

                        sound_ok()

                    else:
                        self.label_status.config(text='Ошибка')

                        sound_error()

                        messagebox.showerror('Ошибка', error_message)

        except queue.Empty:
            pass

        self.label_status.update_idletasks()

        self.root.after(100, self._poll_status_queue)

    def _run_download_in_thread(self, params: list) -> None:
        def worker():
            try:
                ok = self.converter_obj.exec_with_progress(params, on_line=self.update_status_line)

            except Exception as error:
                self._status_queue.put(('done', (False, str(error))))

                return

            self._status_queue.put(('done', (ok, 'Ошибка скачивания')))

        threading.Thread(target=worker, daemon=True).start()

    @validate_call
    def download_archive(self, height: int = 720, convert_to_mp4: bool = False):
        self.status = 'Старт'

        # self.update_yt_dlp()

        url = self.tkinter_root.clipboard_get()

        if not isinstance(url, str) or not re.match(r'^http', url):
            self.sound_error()

            messagebox.showerror('Ошибка', 'Неправильный url')

            raise ValueError('Неправильный url')

        params = []

        params += [self.yt_dlp_file, url]

        params += ['--ffmpeg-location', self.converter_obj.ffmpeg_file.parent.as_posix()]

        params += ['--embed-chapters']
        params += ['--yes-playlist']
        params += ['--embed-subs']
        params += ['--sub-langs', 'ru,en,ua,ja']
        params += ['--write-auto-subs']
        params += ['--ignore-errors']
        params += ['--force-overwrites']
        params += ['--newline']
        params += ['--progress']

        if convert_to_mp4:
            params += ['--recode-video', 'mp4']

        params += ['-f', f'bestvideo[height<={height}]+bestaudio']
        params += ['-o', self.file_name_format]

        self._run_download_in_thread(params)

    def update_yt_dlp(self) -> None:
        if not self.yt_dlp_file.is_file():
            self.download_yt_dlp()

            return

        params = []

        params += [self.yt_dlp_file, '-U']

        self.converter_obj.exec_ffmpeg(params)

    def download_yt_dlp(self) -> None:
        self.status = 'Скачивание yt-dlp'

        try:
            urllib.request.urlretrieve(YT_DLP_DOWNLOAD_URL, self.yt_dlp_file)

        except urllib.error.URLError as error:
            self.sound_error()

            if self.yt_dlp_file.is_file():
                self.yt_dlp_file.unlink()

            messagebox.showerror('Ошибка', f'Не удалось скачать yt-dlp: {error}')

            raise

        self.status = 'Ок'

    def create_link(self):
        initial_dir = DOWNLOAD_DIR

        len_initial_dir_parts = len(initial_dir.parts)

        if source := fd.askopenfilename(initialdir=initial_dir, title='Источник для ссылки'):

            source = Path(source)

            # source = Path(*source.parts[len_initial_dir_parts:])

            if target := fd.askdirectory(initialdir=DOWNLOAD_DIR.as_posix(), title='В какую папку ссылка'):

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

            sound_ok()

            self.status = 'Ок'

        elif size_video_var == '1':
            self.download_archive(height=1080, convert_to_mp4=convert_to_mp4)

        else:
            self.sound_error()

            raise ValueError('Не найдено значение для меню')

    @validate_call
    def download_any(self, height: int | str | None = None):

        self.status = 'Старт'

        url = self.tkinter_root.clipboard_get()

        if not isinstance(url, str) or not re.match(r'^http', url):
            self.sound_error()

            messagebox.showerror('Ошибка', 'Неправильный url')

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
        params += ['--newline']
        params += ['--progress']

        if height:
            height = int(height)

            params += ['-f', f'best[height={height}]']

        params += ['-o', self.file_name_format]

        self._run_download_in_thread(params)

    def convert_to_telegram(self, tune: str, height: int | str | None = None, start_time: str = '00:00:00', end_time: str | None = None):

        file = self.open_file_with_cache(start_dir=DOWNLOAD_DIR.as_posix(), cache_key='convert_to_telegram')

        if file.as_posix() == '.':
            self.sound_error()

            return

        preview = self.open_file_with_cache(start_dir=DOWNLOAD_DIR.as_posix(), cache_key='convert_to_telegram_preview')

        if preview.as_posix() == '.':
            preview = self.converter_obj.extract_screenshot_from_video(
                out_file_image=VIDEOS_OUTPUT_DIR / 'screenshot.png',
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

        preset = self.converter_obj.PresetH264.veryslow
        tune = self.converter_obj.TuneH264[tune]
        audio_bitrate_kilobit = 196
        crf = 24

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
            crf=30,
            # start_time='02:20:00',
            # end_time='02:30:00',
            # height=144,
            # fps=30,
            preset=self.converter_obj.PresetH264.ultrafast,
            tune=self.converter_obj.TuneH264.film,
            # copy_audio=True,
            # copy_video=True

        )

        sound_ok()

    def convert_to_mp3(self):
        self.status = 'Статус'

        res = self.converter_obj.mp3(quality_vbr=0, start_time='00:00:00')

        self.converter_obj.extract_screenshot_from_video(
            file=res.in_file,
            out_file_image=VIDEOS_OUTPUT_DIR / 'screenshot.png',
            start_time='00:00:03'
        )

        sound_ok()

        self.status = 'Ок'

    def convert_to_vorbis(self):
        self.status = 'Статус'

        res = self.converter_obj.vorbis(quality_vbr=7, start_time='00:00:00')

        self.converter_obj.extract_screenshot_from_video(
            file=res.in_file,
            out_file_image=VIDEOS_OUTPUT_DIR / 'screenshot.png',
            start_time='00:00:03'
        )

        sound_ok()

        self.status = 'Ок'

    def convert_to_flac(self):
        self.status = 'Статус'

        res = self.converter_obj.flac(compression_level=12, start_time='00:00:00')

        self.converter_obj.extract_screenshot_from_video(
            file=res.in_file,
            out_file_image=VIDEOS_OUTPUT_DIR / 'screenshot.png',
            start_time='00:00:03'
        )

        self.status = 'Ок'

        sound_ok()

    def open_file_with_cache(self, start_dir: Path | str, cache_key: str):

        start_dir = Path(start_dir)

        cache_item = self.cache.get(cache_key)

        if not cache_item:
            file = fd.askopenfilename(initialdir=start_dir)

        else:
            file_path = Path(cache_item)

            if file_path.is_file():
                file = fd.askopenfilename(initialfile=cache_item)

            else:
                file = fd.askopenfilename(initialdir=cache_item)

        file = Path(file)

        if file.is_file():
            self.cache.set(cache_key, file.as_posix())

        return file

    @validate_call
    def download_audio(self):
        self.status = 'Старт'

        url = self.tkinter_root.clipboard_get()

        if not isinstance(url, str) or not re.match(r'^http', url):
            self.sound_error()

            messagebox.showerror('Ошибка', 'Неправильный url')

            raise ValueError('Неправильный url')

        params = []

        params += [self.yt_dlp_file, url]

        params += ['--ffmpeg-location', self.converter_obj.ffmpeg_file.parent.as_posix()]

        params += ['--extract-audio']
        params += ['--force-overwrites']
        # params += ['--audio-format', 'flac']
        params += ['--embed-chapters']
        params += ['--yes-playlist']
        params += ['--embed-subs']
        params += ['--sub-langs', 'ru,en,ua,ja']
        params += ['--write-auto-subs']
        params += ['--newline']
        params += ['--progress']

        params += ['-f', f'bestaudio']
        params += ['-o', self.file_name_format_audio]

        self._run_download_in_thread(params)

    def update_status_line(self, line: str) -> None:
        self._status_queue.put(('status', line[:120]))

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


youtube = Youtube()
