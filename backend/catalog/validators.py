"""File-upload validation for catalog images.

Enforced at the model layer (field validators run during ``full_clean()`` /
form and serializer validation) — never only on the client.

At the model level the field value arrives wrapped in a ``FieldFile``, so the
validators unwrap to the underlying file where needed.
"""

import os

from django.core.exceptions import ValidationError
from django.template.defaultfilters import filesizeformat
from PIL import Image

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def _underlying_file(value):
    """Return the raw uploaded file behind a possible FieldFile wrapper."""
    return getattr(value, "file", value)


def validate_image_extension(value):
    """Reject filenames whose extension is not an allowed image format."""
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image format '{ext or '(none)'}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )


def validate_image_mime(value):
    """Reject uploads whose reported MIME type is not an allowed image type."""
    upload = _underlying_file(value)
    mime = getattr(upload, "content_type", None)
    if mime and mime not in ALLOWED_IMAGE_MIME_TYPES:
        raise ValidationError(
            f"Unsupported image type '{mime}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_MIME_TYPES))}."
        )


def validate_image_size(value):
    """Reject uploads larger than ``MAX_IMAGE_SIZE``."""
    if value.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            f"Image file too large. Maximum size is {filesizeformat(MAX_IMAGE_SIZE)}."
        )


def validate_image_content(value):
    """Reject files that are not actually decodable images."""
    upload = _underlying_file(value)
    try:
        upload.seek(0)
        image = Image.open(upload)
        image.verify()
        upload.seek(0)
    except Exception as exc:
        raise ValidationError("Uploaded file is not a valid image.") from exc


# Size/extension/MIME checks run before the expensive content decode.
IMAGE_VALIDATORS = [
    validate_image_extension,
    validate_image_mime,
    validate_image_size,
    validate_image_content,
]
