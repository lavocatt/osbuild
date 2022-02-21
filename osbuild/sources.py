import abc
import contextlib
import os
import json
import tempfile
from typing import List, Dict
from enum import Enum

from osbuild.formats_common import OSBuildError
from . import host
from .objectstore import ObjectStore
from .util.types import PathLike


class SourceErrorKind(Enum):
    UNKNOWN = 0
    CHECKSUM = 1
    # OSTree errors
    OSTREE_REMOTE_ADD = 2
    OSTREE_GPG_IMPORT = 3
    OSTREE_PULL = 4
    OSTREE_REMOTE_DELETE = 5
    # Skopeo errors
    SKOPEO_COPY = 6
    SKOPEO_INSPECT = 7
    # Curl errors
    CURL_BAD_INPUT = 8
    CURL_INTERNAL_ERROR = 9
    CURL_NETWORKING = 10
    CURL_CREDENTIALS = 11
    CURL_STORAGE = 12
    CURL_SECURITY = 13


class SourceError(OSBuildError):
    _ID = 1000

    def __init__(self, kind: SourceErrorKind, message: str, source: str):
        self.kind = kind
        self.message = message
        self.source = source
        super().__init__(message)

    @property
    def code(self):
        return SourceErrorKind(self.kind).name

    @property
    def details(self):
        return {"source": self.source}

    @property
    def ID(self):
        return SourceError._ID+self.kind.value

    def to_dict(self) -> Dict:
        return {
            "kind": self.kind.value,
            "message": self.message,
            "source": self.source
        }

    @staticmethod
    def from_dict(obj: Dict):
        kind = obj["kind"]
        message = obj["message"]
        source = obj["source"]
        return SourceError(SourceErrorKind(kind), message, source)


class Source:
    """
    A single source with is corresponding options.
    """

    def __init__(self, info, items, options) -> None:
        self.info = info
        self.items = items or {}
        self.options = options

    @staticmethod
    def raise_error(obj: Dict, _fds: List = None):
        raise SourceError.from_dict(obj)

    def download(self, mgr: host.ServiceManager, store: ObjectStore, libdir: PathLike):
        source = self.info.name
        cache = os.path.join(store.store, "sources")

        args = {
            "options": self.options,
            "cache": cache,
            "output": None,
            "checksums": [],
            "libdir": os.fspath(libdir)
        }

        client = mgr.start(f"source/{source}", self.info.path)

        with self.make_items_file(store.tmp) as fd:
            client.call_with_fds("download", args, [fd], on_signal=Source.raise_error)

    @contextlib.contextmanager
    def make_items_file(self, tmp):
        with tempfile.TemporaryFile("w+", dir=tmp, encoding="utf-8") as f:
            json.dump(self.items, f)
            f.seek(0)
            yield f.fileno()


class SourceService(host.Service):
    """Source host service"""

    def signal_error(self, item: SourceError):
        self.emit_signal(item.to_dict())

    @abc.abstractmethod
    def download(self, items, cache, options):
        pass

    def dispatch(self, method: str, args, fds):
        if method == "download":
            with os.fdopen(fds.steal(0)) as f:
                items = json.load(f)

            r = self.download(items,
                              args["cache"],
                              args["options"])
            return r, None

        raise host.ProtocolError("Unknown method")
