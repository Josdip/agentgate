"""Execute bounded file operations inside an operator-selected directory."""

import os
import stat
from contextlib import ExitStack, contextmanager
from pathlib import PurePosixPath
from uuid import uuid4

MAX_BYTES = 128_000


def relative_path(value):
    path = PurePosixPath(value)
    if (
        str(path) != value
        or path.is_absolute()
        or not path.parts
        or any(
            part.startswith(".") or part.endswith((".pem", ".key", ".db", ".sqlite3"))
            for part in path.parts
        )
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError("Use a normalized, non-private path inside the managed project.")
    return path


class ProjectFiles:
    def __init__(self, root):
        self.root = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        os.close(self.root)

    @contextmanager
    def parent(self, target):
        path = relative_path(target)
        with ExitStack() as directories:
            parent = self.root
            for part in path.parts[:-1]:
                parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                directories.callback(os.close, parent)
            yield parent, path.name

    @staticmethod
    def read(parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
                raise ValueError("Expected a bounded regular file with a single link.")
            content = file.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES or b"\0" in content:
            raise ValueError("Expected bounded UTF-8 text.")
        return content.decode("utf-8")

    def execute(self, action):
        with self.parent(action.path) as (parent, name):
            if action.tool == "read_file":
                lines = self.read(parent, name).splitlines()
                return "\n".join(
                    lines[action.start_line - 1 : action.start_line - 1 + action.line_count]
                )[:24_000]

            try:
                self.read(parent, name)
            except FileNotFoundError:
                pass
            temporary = f".agentgate-{uuid4().hex}"
            fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            try:
                with os.fdopen(fd, "wb") as file:
                    file.write(action.content.encode())
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
                os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass
            return "Project file saved."
