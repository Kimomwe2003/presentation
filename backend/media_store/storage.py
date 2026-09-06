"""FileSystemStorage that also keeps a durable copy of every file in Postgres.

Reading prefers the filesystem; if the disk copy is missing the bytes are
served from the :class:`StoredMedia` table. This keeps ``/media/...`` URLs
working after redeploys or database restores that lose the media folder.
"""

import io
import logging

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage

log = logging.getLogger("media_store.storage")


class DbBackedStorage(FileSystemStorage):
    def _save(self, name, content):
        # Read the bytes once so we can persist them, then let the base class
        # write the filesystem copy (it re-reads from the start of the file).
        try:
            content.seek(0)
            data = content.read()
        except Exception as exc:  # noqa: BLE001 - never block the file write
            log.warning("media_store: could not read content of %s: %s", name, exc)
            return super()._save(name, content)

        name = super()._save(name, content)

        try:
            self._persist(name, data)
        except Exception as exc:  # noqa: BLE001 - disk save is the primary path
            log.warning("media_store: DB persist of %s failed: %s", name, exc)
        return name

    def _persist(self, name, data: bytes) -> None:
        from .models import StoredMedia

        StoredMedia.objects.update_or_create(
            name=name,
            defaults={
                "data": data,
                "content_type": _guess_content_type(name),
                "size": len(data),
                "sha256": StoredMedia.digest_for(data),
            },
        )

    def _open(self, name, mode="rb"):
        if mode != "rb":
            return super()._open(name, mode)
        try:
            return super()._open(name, "rb")
        except (FileNotFoundError, OSError):
            pass

        # The name is derived from storage so it is safe, but harden anyway.
        name = self.get_valid_name(name)

        from .models import StoredMedia

        try:
            row = StoredMedia.objects.get(name=name)
        except StoredMedia.DoesNotExist as exc:
            raise FileNotFoundError(f"No medium stored for {name}") from exc
        return io.BytesIO(bytes(row.data))

    def exists(self, name):
        if self._exist_on_disk(name):
            return True
        from .models import StoredMedia

        try:
            StoredMedia.objects.get(name=self.get_valid_name(name))
        except (StoredMedia.DoesNotExist, SuspiciousFileOperation):
            return False

    def _exist_on_disk(self, name):
        try:
            return super().exists(name)
        except SuspiciousFileOperation:
            return False

    def delete(self, name):
        super().delete(name)
        from .models import StoredMedia

        try:
            StoredMedia.objects.filter(name=name).delete()
        except Exception as exc:  # noqa: BLE001
            log.warning("media_store: DB delete of %s failed: %s", name, exc)

    # Helpers -------------------------------------------------------------

    def is_durable(self, name) -> bool:
        """True when a database copy of ``name`` exists (survives a redeploy)."""
        from .models import StoredMedia

        try:
            return StoredMedia.objects.filter(
                name=self.get_valid_name(name)
            ).exists()
        except SuspiciousFileOperation:
            return False


def _guess_content_type(name: str) -> str:
    import mimetypes

    return mimetypes.guess_type(name)[0] or "application/octet-stream"
