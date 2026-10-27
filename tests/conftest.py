import pytest

import vapoursynth as vs

core = vs.core


@pytest.fixture
def blank_video() -> vs.VideoNode:
    return core.std.BlankClip(width=640, height=480, format=vs.RGB24, fpsnum=24, fpsden=1, length=100)


@pytest.fixture
def blank_audio() -> vs.AudioNode:
    return core.std.BlankAudio(channels=[vs.FRONT_LEFT, vs.FRONT_RIGHT], samplerate=44100, bits=16, length=44100)


@pytest.fixture
def video_pipeline(blank_video: vs.VideoNode) -> vs.VideoNode:
    return blank_video.text.Text("Test Header").resize.Bicubic(
        width=1280, height=720, format=vs.YUV420P8, matrix_s="709"
    )


@pytest.fixture
def diamond_video_dag(video_pipeline: vs.VideoNode) -> vs.VideoNode:
    invert = core.std.Invert(video_pipeline)
    return core.std.Splice([video_pipeline, invert])
