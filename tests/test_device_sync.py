import os
from pathlib import Path, PosixPath
from unittest.mock import call

import pytest

import belay
import belay.device


def uint(x):
    """For patching micropython.viper code for testing."""
    return x % (1 << 32)


def __belay_ilistdir(x):
    for name in os.listdir(x):
        stat = os.stat(x + "/" + name)  # noqa: PL116
        yield (name, stat.st_mode, stat.st_ino)


@pytest.fixture
def mock_pyboard(mocker):
    def mock_init(self, *args, **kwargs):
        self.serial = None

    exec_side_effect = [b'_BELAYR("micropython", (1, 19, 1), "rp2")\r\n'] * 100

    mocker.patch.object(belay.device.Pyboard, "__init__", mock_init)
    mocker.patch("belay.device.Pyboard.enter_raw_repl", return_value=None)
    mocker.patch("belay.device.Pyboard.exec", side_effect=exec_side_effect)
    mocker.patch("belay.device.Pyboard.fs_put")


@pytest.fixture
def mock_device(mock_pyboard):
    device = belay.Device()
    return device


@pytest.fixture
def sync_path(tmp_path):
    (tmp_path / "alpha.py").write_text("def alpha():\n    pass")
    (tmp_path / "bar.txt").write_text("bar contents")
    (tmp_path / "foo.txt").write_text("foo contents")
    (tmp_path / "folder1" / "folder1_1").mkdir(parents=True)
    (tmp_path / "folder1" / "file1.txt").write_text("file1 contents")
    (tmp_path / "folder1" / "folder1_1" / "file1_1.txt").write_text("file1_1 contents")

    return tmp_path


def _patch_micropython_code(snippet):
    # Patch out micropython stuff
    lines = snippet.split("\n")
    lines = [x for x in lines if "micropython" not in x]
    snippet = "\n".join(lines)
    snippet = snippet.replace("os.ilistdir", "ilistdir")
    return snippet


@pytest.fixture
def sync_begin():
    snippet = belay.device._read_snippet("sync_begin")
    snippet = _patch_micropython_code(snippet)
    exec(snippet, globals())


@pytest.fixture
def hf():
    snippet = belay.device._read_snippet("hf")
    snippet = _patch_micropython_code(snippet)
    exec(snippet, globals())


@pytest.fixture
def hf_native():
    snippet = belay.device._read_snippet("hf_native")
    snippet = _patch_micropython_code(snippet)
    exec(snippet, globals())


@pytest.fixture
def hf_viper():
    snippet = belay.device._read_snippet("hf_viper")
    snippet = _patch_micropython_code(snippet)
    exec(snippet, globals())


def test_sync_local_belay_hf(tmp_path):
    """Test local FNV-1a hash implementation.

    Test vector from: http://www.isthe.com/chongo/src/fnv/test_fnv.c
    """
    f = tmp_path / "test_file"
    f.write_text("foobar")
    actual = belay.device._local_hash_file(f)
    assert actual == 0xBF9CF968


def test_sync_device_belay_hf(hf, tmp_path):
    """Test on-device FNV-1a hash implementation."""
    f = tmp_path / "test_file"
    f.write_text("foobar")
    buf = memoryview(bytearray(4096))
    actual = __belay_hf(str(f), buf)  # noqa: F821
    assert actual == 0xBF9CF968


def test_sync_device_belay_hf_native(hf_native, tmp_path):
    """Test on-device FNV-1a native hash implementation."""
    f = tmp_path / "test_file"
    f.write_text("foobar")
    buf = memoryview(bytearray(4096))
    actual = __belay_hf(str(f), buf)  # noqa: F821
    assert actual == 0xBF9CF968


def test_sync_device_belay_hf_viper(hf_viper, tmp_path):
    """Test on-device FNV-1a viper hash implementation."""
    f = tmp_path / "test_file"
    f.write_text("foobar")
    buf = memoryview(bytearray(4096))
    actual = __belay_hf(str(f), buf)  # noqa: F821
    assert actual == 0xBF9CF968


def test_sync_device_belay_hfs(sync_begin, capsys, tmp_path):
    fooba_file = tmp_path / "fooba_file"
    fooba_file.write_text("fooba")

    foobar_file = tmp_path / "foobar_file"
    foobar_file.write_text("foobar")

    return_value = __belay_hfs([str(fooba_file), str(foobar_file)])  # noqa: F821
    assert return_value is None
    captured = capsys.readouterr()
    assert captured.out == f"_BELAYR[{0x39aaa18a}, {0xbf9cf968}]\n"


def test_sync_device_belay_mkdirs(sync_begin, tmp_path):
    paths = [
        tmp_path,
        tmp_path / "foo1",
        tmp_path / "foo1" / "foo2",
        tmp_path / "bar1",
        tmp_path / "bar1" / "bar2",
    ]
    paths = [str(x) for x in paths]
    __belay_mkdirs(paths)  # noqa: F821
    assert (tmp_path).is_dir()
    assert (tmp_path / "foo1").is_dir()
    assert (tmp_path / "foo1" / "foo2").is_dir()
    assert (tmp_path / "bar1").is_dir()
    assert (tmp_path / "bar1" / "bar2").is_dir()


def test_sync_device_belay_fs_basic(sync_begin, tmp_path):
    expected_files = {
        tmp_path / "foo1" / "foo2" / "foo_file.py",
        tmp_path / "bar1" / "bar2" / "bar_file.py",
    }
    expected_dirs = {
        tmp_path / "foo1",
        tmp_path / "foo1" / "foo2",
        tmp_path / "bar1",
        tmp_path / "bar1" / "bar2",
    }
    for f in expected_files:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.touch()

    __belay_fs(str(tmp_path))  # noqa: F821
    _all_files = {Path(x) for x in all_files}  # noqa: F821
    _all_dirs = {Path(x) for x in all_dirs}  # noqa: F821

    assert _all_files == expected_files
    assert _all_dirs == expected_dirs


def test_sync_device_belay_fs_does_not_exist(sync_begin, tmp_path):
    non_existing_dir = tmp_path / "does_not_exist"
    __belay_fs(str(non_existing_dir))  # noqa: F821
    assert all_files == set()  # noqa: F821
    assert all_dirs == []  # noqa: F821


def test_device_sync_empty_remote(mocker, mock_device, sync_path):
    payload = ("_BELAYR" + repr([b""] * 5) + "\r\n").encode("utf-8")
    mock_device._board.exec = mocker.MagicMock(return_value=payload)

    mock_device.sync(sync_path)

    mock_device._board.exec.assert_has_calls(
        [
            call(
                "for x in['/alpha.py','/bar.txt','/folder1/file1.txt','/folder1/folder1_1/file1_1.txt','/foo.txt','/boot.py','/webrepl_cfg.py']:\n all_files.discard(x)"
            ),
            call("__belay_mkdirs(['/folder1','/folder1/folder1_1'])"),
            call(
                "__belay_hfs(['/alpha.py','/bar.txt','/folder1/file1.txt','/folder1/folder1_1/file1_1.txt','/foo.txt'])"
            ),
        ]
    )

    mock_device._board.fs_put.assert_has_calls(
        [
            call(sync_path / "bar.txt", "/bar.txt"),
            call(sync_path / "folder1/file1.txt", "/folder1/file1.txt"),
            call(
                sync_path / "folder1/folder1_1/file1_1.txt",
                "/folder1/folder1_1/file1_1.txt",
            ),
            call(sync_path / "foo.txt", "/foo.txt"),
        ]
    )


def test_device_sync_partial_remote(mocker, mock_device, sync_path):
    def __belay_hfs(fns):
        out = []
        for fn in fns:
            local_fn = sync_path / fn[1:]
            if local_fn.stem.endswith("1"):
                out.append(b"\x00")
            else:
                out.append(belay.device._local_hash_file(local_fn))
        return out

    def side_effect(cmd):
        if not cmd.startswith("__belay_hfs"):
            return b""
        nonlocal __belay_hfs
        return ("_BELAYR" + repr(eval(cmd)) + "\r\n").encode("utf-8")

    mock_device._board.exec = mocker.MagicMock(side_effect=side_effect)

    mock_device.sync(sync_path)

    mock_device._board.fs_put.assert_has_calls(
        [
            call(sync_path / "folder1/file1.txt", "/folder1/file1.txt"),
            call(
                sync_path / "folder1/folder1_1/file1_1.txt",
                "/folder1/folder1_1/file1_1.txt",
            ),
        ]
    )


def test_discover_files_dirs_dir(tmp_path):
    (tmp_path / "file1.ext").touch()
    (tmp_path / "file2.ext").touch()
    (tmp_path / "folder1").mkdir()
    (tmp_path / "folder1" / "file3.ext").touch()

    remote_dir = "/foo/bar"
    src_files, src_dirs, dst_files = belay.device._discover_files_dirs(
        remote_dir=remote_dir,
        local_file_or_folder=tmp_path,
    )

    src_files = [x.relative_to(tmp_path) for x in src_files]
    src_dirs = [x.relative_to(tmp_path) for x in src_dirs]
    assert src_files == [
        PosixPath("file1.ext"),
        PosixPath("file2.ext"),
        PosixPath("folder1/file3.ext"),
    ]
    assert src_dirs == [PosixPath("folder1")]
    assert dst_files == [
        PosixPath("/foo/bar/file1.ext"),
        PosixPath("/foo/bar/file2.ext"),
        PosixPath("/foo/bar/folder1/file3.ext"),
    ]


def test_discover_files_dirs_dir_ignore(tmp_path):
    (tmp_path / "file1.ext").touch()
    (tmp_path / "file2.pyc").touch()
    (tmp_path / "folder1").mkdir()
    (tmp_path / "folder1" / "file3.ext").touch()

    remote_dir = "/foo/bar"
    src_files, src_dirs, dst_files = belay.device._discover_files_dirs(
        remote_dir=remote_dir,
        local_file_or_folder=tmp_path,
        ignore=["*.pyc"],
    )

    src_files = [x.relative_to(tmp_path) for x in src_files]
    src_dirs = [x.relative_to(tmp_path) for x in src_dirs]
    assert src_files == [
        PosixPath("file1.ext"),
        PosixPath("folder1/file3.ext"),
    ]
    assert src_dirs == [PosixPath("folder1")]
    assert dst_files == [
        PosixPath("/foo/bar/file1.ext"),
        PosixPath("/foo/bar/folder1/file3.ext"),
    ]


def test_discover_files_dirs_empty(tmp_path):
    remote_dir = "/foo/bar"
    src_files, src_dirs, dst_files = belay.device._discover_files_dirs(
        remote_dir=remote_dir,
        local_file_or_folder=tmp_path,
    )

    assert src_files == []
    assert src_dirs == []
    assert dst_files == []


def test_discover_files_dirs_single_file(tmp_path):
    single_file = tmp_path / "file1.ext"
    single_file.touch()

    remote_dir = "/foo/bar"
    src_files, src_dirs, dst_files = belay.device._discover_files_dirs(
        remote_dir=remote_dir,
        local_file_or_folder=single_file,
    )

    src_files = [x.relative_to(tmp_path) for x in src_files]
    src_dirs = [x.relative_to(tmp_path) for x in src_dirs]
    assert src_files == [PosixPath("file1.ext")]
    assert src_dirs == []
    assert dst_files == [PosixPath("/foo/bar/file1.ext")]


def test_preprocess_keep_none_root():
    actual = belay.device._preprocess_keep(None, "/")
    assert actual == ["/boot.py", "/webrepl_cfg.py"]


def test_preprocess_keep_none_nonroot():
    actual = belay.device._preprocess_keep(None, "/foo")
    assert actual == []


def test_preprocess_keep_list():
    actual = belay.device._preprocess_keep(["foo"], "/")
    assert actual == ["/foo"]


def test_preprocess_keep_str():
    actual = belay.device._preprocess_keep("foo", "/")
    assert actual == ["/foo"]


def test_preprocess_keep_bool_true():
    actual = belay.device._preprocess_keep(True, "/")
    assert actual == []


def test_preprocess_keep_bool_false():
    actual = belay.device._preprocess_keep(False, "/")
    assert actual == []


def test_preprocess_ignore_none():
    actual = belay.device._preprocess_ignore(None)
    assert actual == ["*.pyc", "__pycache__", ".DS_Store", ".pytest_cache"]


def test_preprocess_ignore_list():
    actual = belay.device._preprocess_ignore(["foo", "bar"])
    assert actual == ["foo", "bar"]


def test_preprocess_ignore_str():
    actual = belay.device._preprocess_ignore("foo")
    assert actual == ["foo"]


def test_preprocess_src_file_default_py(tmp_path):
    actual = belay.device._preprocess_src_file(tmp_path, "foo/bar/baz.py", False, None)
    assert actual == Path("foo/bar/baz.py")


def test_preprocess_src_file_default_generic(tmp_path):
    actual = belay.device._preprocess_src_file(
        tmp_path, "foo/bar/baz.generic", False, None
    )
    assert actual == Path("foo/bar/baz.generic")


def test_generate_dst_dirs():
    dst = "/foo/bar"
    src = Path("/bloop/bleep")
    src_dirs = [
        src / "dir1",
        src / "dir1" / "dir1_1",
        src / "dir1" / "dir1_2",
        src / "dir2",
        src / "dir2" / "dir2_1",
        src / "dir2" / "dir2_2",
    ]
    dst_dirs = belay.device._generate_dst_dirs(dst, src, src_dirs)
    assert dst_dirs == [
        "/foo",
        "/foo/bar",
        "/foo/bar/dir1",
        "/foo/bar/dir1/dir1_1",
        "/foo/bar/dir1/dir1_2",
        "/foo/bar/dir2",
        "/foo/bar/dir2/dir2_1",
        "/foo/bar/dir2/dir2_2",
    ]
