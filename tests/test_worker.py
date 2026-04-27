import shutil
from pathlib import Path
from src.background_worker import process_file

def test_process_file(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()

    # 1. Non-PDF/EPUB files are ignored and stay in place
    txt_file = incoming / "test.txt"
    txt_file.write_text("dummy")
    process_file(txt_file, processed)
    assert txt_file.exists()
    assert not (processed / "test.txt").exists()

    # 2. Valid .epub is moved to processed_dir with sanitized name
    epub_file = incoming / "My Test Book!.epub"
    epub_file.write_text("dummy epub")
    process_file(epub_file, processed)
    assert not epub_file.exists()
    assert (processed / "my_test_book.epub").exists()

    # 3. Duplicate filename gets a _1 suffix
    epub_file_2 = incoming / "My Test Book!.epub"
    epub_file_2.write_text("dummy epub 2")
    process_file(epub_file_2, processed)
    assert not epub_file_2.exists()
    assert (processed / "my_test_book_1.epub").exists()
