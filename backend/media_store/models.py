import hashlib

from django.db import models


class StoredMedia(models.Model):
    """Durable copy of a media file referenced from the database.

    ``name`` is the storage key (e.g. ``products/48/9527ea…jpg``), identical to
    the FileSystemStorage path. The bytes live in :attr:`data` so the file is
    recoverable even when the filesystem copy is gone.
    """

    name = models.CharField(max_length=500, primary_key=True)
    data = models.BinaryField()
    content_type = models.CharField(max_length=120, default="")
    size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "stored media"
        verbose_name_plural = "stored media"

    def __str__(self):
        return self.name

    @classmethod
    def digest_for(cls, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
