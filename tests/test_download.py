import hashlib
import io
import zipfile
from pathlib import Path

from scrcpy_gui import download


def test_verify_and_extract_tiny_zip(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("inner/hello.txt", b"hello")
    raw = buf.getvalue()
    zip_path = tmp_path / "a.zip"
    zip_path.write_bytes(raw)
    want = hashlib.sha256(raw).hexdigest()
    download.verify_file_sha256(zip_path, want)
    out = tmp_path / "out"
    download.extract_zip(zip_path, out)
    assert (out / "inner" / "hello.txt").read_text() == "hello"


def test_verify_rejects_wrong_hash(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    try:
        download.verify_file_sha256(p, "0" * 64)
    except RuntimeError as e:
        assert "hash mismatch" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
