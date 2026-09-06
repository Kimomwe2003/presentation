"""Serves ``/media/...`` from the filesystem first, the database as a fallback.

Replaces ``django.views.static.serve`` so that uploaded images keep working
even when the media folder is missing (e.g. after a redeploy): the bytes are
read back from :class:`StoredMedia` in that case.
"""

import mimetypes
import os
import posixpath
from io import BytesIO

from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponseNotFound

from .models import StoredMedia


def serve_media_file(request, path):
    del request
    if path is None:
        return HttpResponseNotFound("Not Found")

    name = posixpath.normpath(path).lstrip("/")
    if name.startswith("..") or name.startswith("/") or not name:
        return HttpResponseNotFound("Not Found")

    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"

    # 1) Filesystem copy (fast path).
    try:
        fs_path = os.path.join(str(default_storage.location), name)
        if os.path.isfile(fs_path) and os.path.getsize(fs_path):
            return FileResponse(open(fs_path, "rb"), content_type=content_type)
    except (OSError, ValueError):
        pass

    # 2) Database copy.
    try:
        row = StoredMedia.objects.get(name=name)
    except StoredMedia.DoesNotExist:
        return HttpResponseNotFound("Not Found")

    return FileResponse(
        BytesIO(bytes(row.data)),
        content_type=row.content_type or content_type,
        filename=os.path.basename(name),
    )
