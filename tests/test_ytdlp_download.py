"""Tests for ytdlp_download service."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from bot.services.ytdlp_download import (
    _work_dir,
    _pick_largest_media,
    _finalize_path,
    _assert_under_limit,
    _validate_media,
    cleanup_download,
    download_audio_format,
    DownloadTooLargeError,
    DownloadQualityError
)

class MockSettings:
    def __init__(self, download_path, max_file_size_mb):
        self.download_path = download_path
        self.max_file_size_mb = max_file_size_mb
    
    @property
    def max_file_size_bytes(self):
        return self.max_file_size_mb * 1024 * 1024

def test_work_dir(tmp_path):
    s = MockSettings(tmp_path, 50)
    wd = _work_dir(s)
    assert wd.exists()
    assert wd.parent == tmp_path

def test_pick_largest_media(tmp_path):
    d = tmp_path / "media"
    d.mkdir()
    f1 = d / "small.mp3"
    f1.write_text("1")
    f2 = d / "large.mp4"
    f2.write_text("12345")
    f3 = d / "skip.jpg"
    f3.write_text("123456789")
    
    largest = _pick_largest_media(d)
    assert largest.name == "large.mp4"

def test_pick_largest_media_no_files(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    with pytest.raises(FileNotFoundError):
        _pick_largest_media(d)

def test_assert_under_limit(tmp_path):
    s = MockSettings(tmp_path, 1) # 1 MB
    f = tmp_path / "file.txt"
    f.write_text("x" * 10)
    _assert_under_limit(f, s) # Should pass
    
    f_large = tmp_path / "large.txt"
    # We can fake the size or just write 1.01 MB
    f_large.write_text("x" * (1024 * 1024 + 10))
    with pytest.raises(DownloadTooLargeError):
        _assert_under_limit(f_large, s)

def test_validate_media(tmp_path):
    f = tmp_path / "media.mp3"
    f.write_text("x" * 1000)
    
    # Valid
    _validate_media(f, min_bytes=500, min_duration=10.0, info={"duration": 15.0})
    
    # Invalid size
    with pytest.raises(DownloadQualityError, match="Archivo demasiado pequeño"):
        _validate_media(f, min_bytes=2000, min_duration=10.0, info={"duration": 15.0})
        
    # Invalid duration
    with pytest.raises(DownloadQualityError, match="Contenido demasiado corto"):
        _validate_media(f, min_bytes=500, min_duration=20.0, info={"duration": 15.0})

def test_cleanup_download(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    f = d / "file.txt"
    f.touch()
    assert d.exists()
    cleanup_download(f)
    assert not d.exists()

def test_download_audio_format_invalid_fmt(tmp_path):
    s = MockSettings(tmp_path, 50)
    with pytest.raises(ValueError, match="Formato no soportado: wav"):
        download_audio_format("http://url", s, "wav")

@patch("bot.services.ytdlp_download.yt_dlp.YoutubeDL")
def test_download_audio_format_success(mock_ytdl_class, tmp_path):
    s = MockSettings(tmp_path, 50)
    mock_instance = MagicMock()
    mock_ytdl_class.return_value.__enter__.return_value = mock_instance
    
    def fake_extract(*args, **kwargs):
        # find the work directory that was created inside tmp_path
        dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        d = dirs[0]
        f = d / "test.mp3"
        f.write_text("x" * 60000)
        # Mock what yt_dlp info looks like
        return {"filepath": str(f), "duration": 15.0}
        
    mock_instance.extract_info.side_effect = fake_extract
    mock_instance.prepare_filename.return_value = "/nonexistent/fake"
    
    path, wd = download_audio_format("http://url", s, "mp3")
    assert path.name == "test.mp3"
    assert wd.exists()


from bot.services.ytdlp_download import (
    download_best_audio,
    download_apple_m4a,
    download_best_video
)


@patch("bot.services.ytdlp_download.yt_dlp.YoutubeDL")
def test_download_best_audio_success(mock_ytdl_class, tmp_path):
    s = MockSettings(tmp_path, 50)
    mock_instance = MagicMock()
    mock_ytdl_class.return_value.__enter__.return_value = mock_instance
    
    def fake_extract(*args, **kwargs):
        dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        d = dirs[0]
        f = d / "best.m4a"
        f.write_text("x" * 60000)
        return {"filepath": str(f), "duration": 15.0}
        
    mock_instance.extract_info.side_effect = fake_extract
    mock_instance.prepare_filename.return_value = "/nonexistent/fake"
    
    path, wd = download_best_audio("http://url", s)
    assert path.name == "best.m4a"
    assert wd.exists()


@patch("bot.services.ytdlp_download.yt_dlp.YoutubeDL")
def test_download_apple_m4a_success(mock_ytdl_class, tmp_path):
    s = MockSettings(tmp_path, 50)
    mock_instance = MagicMock()
    mock_ytdl_class.return_value.__enter__.return_value = mock_instance
    
    def fake_extract(*args, **kwargs):
        dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        d = dirs[0]
        f = d / "apple.m4a"
        f.write_text("x" * 60000)
        return {"filepath": str(f), "duration": 15.0}
        
    mock_instance.extract_info.side_effect = fake_extract
    mock_instance.prepare_filename.return_value = "/nonexistent/fake"
    
    path, wd = download_apple_m4a("http://url", s)
    assert path.name == "apple.m4a"
    assert wd.exists()


@patch("bot.services.ytdlp_download.yt_dlp.YoutubeDL")
def test_download_best_video_success(mock_ytdl_class, tmp_path):
    s = MockSettings(tmp_path, 50)
    mock_instance = MagicMock()
    mock_ytdl_class.return_value.__enter__.return_value = mock_instance
    
    def fake_extract(*args, **kwargs):
        dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
        d = dirs[0]
        f = d / "video.mp4"
        f.write_text("x" * 600000)
        return {"filepath": str(f), "duration": 15.0}
        
    mock_instance.extract_info.side_effect = fake_extract
    mock_instance.prepare_filename.return_value = "/nonexistent/fake"
    
    path, wd = download_best_video("http://url", s)
    assert path.name == "video.mp4"
    assert wd.exists()
