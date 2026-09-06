import io
import mimetypes
import os
import random

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from media_store.models import StoredMedia


class Command(BaseCommand):
    help = (
        "Persist every file under MEDIA_ROOT into the database media store, "
        "and regenerate any product/profile image whose bytes are missing "
        "from both disk and the database (e.g. after a database restore)."
    )

    def handle(self, *args, **options):
        persisted = self.backfill_disk()
        self.stdout.write(self.style.SUCCESS(f"backfilled {persisted} file(s) from disk"))
        count = self.regenerate_missing()
        self.stdout.write(self.style.SUCCESS(f"regenerated {count} missing image(s)"))

    def backfill_disk(self):
        from accounts.models import Profile
        from catalog.models import ProductImage

        names = set()
        for row in ProductImage.objects.all():
            if row.image.name:
                names.add(row.image.name)
        for row in Profile.objects.exclude(profile_picture=""):
            if row.profile_picture.name:
                names.add(row.profile_picture.name)

        count = 0
        for name in names:
            if StoredMedia.objects.filter(name=name).exists():
                continue
            full = os.path.join(settings.MEDIA_ROOT, name)
            if not os.path.isfile(full):
                continue
            with open(full, "rb") as fh:
                data = fh.read()
            if not data:
                continue
            StoredMedia.objects.create(
                name=name,
                data=data,
                content_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
                size=len(data),
                sha256=StoredMedia.digest_for(data),
            )
            count += 1
        return count

    def regenerate_missing(self):
        from django.core.files.images import ImageFile

        from accounts.models import Profile
        from catalog.models import ProductImage

        count = 0
        colors = ["#1f2937", "#7c3aed", "#0e7490", "#b45309", "#be123c", "#15803d"]

        for row in ProductImage.objects.select_related("product").all():
            name = row.image.name
            if not name:
                continue
            if self._bytes_available(name):
                continue
            label = row.product.name[:20] or "Item"
            blob = _make_placeholder(label, random.choice(colors))
            row.image.save(name, ImageFile(io.BytesIO(blob)), save=True)
            count += 1

        for row in Profile.objects.exclude(profile_picture=""):
            name = row.profile_picture.name
            if not name:
                continue
            if self._bytes_available(name):
                continue
            blob = _make_placeholder("R", random.choice(colors), size=256)
            row.profile_picture.save(name, ImageFile(io.BytesIO(blob)), save=True)
            count += 1

        return count

    def _bytes_available(self, name: str) -> bool:
        try:
            full = os.path.join(settings.MEDIA_ROOT, name)
            if os.path.isfile(full) and os.path.getsize(full) > 0:
                return True
            return StoredMedia.objects.filter(name=name).exists()
        except Exception:  # noqa: BLE001
            return False


def _make_placeholder(label, hex_color, size=800):
    r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
    img = Image.new("RGB", (size, size), (r, g, b))
    draw = ImageDraw.Draw(img)
    for i in range(0, size, 40):
        draw.line([(i, 0), (0, i)], fill=(255, 255, 255), width=1)
    draw.ellipse(
        [size * 0.22, size * 0.22, size * 0.78, size * 0.78],
        fill=(r, g, b),
        outline=(255, 255, 255),
        width=8,
    )
    try:
        draw.text((size / 2, size * 0.82), label, anchor="mm", fill=(255, 255, 255))
    except TypeError:
        draw.text((int(size / 2), int(size * 0.82)), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()
