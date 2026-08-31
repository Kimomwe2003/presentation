"""Smoke tests: project boots, settings load, and PostgreSQL is reachable."""

import pytest
from django.conf import settings
from django.db import connection


def test_project_boots_and_settings_load():
    assert settings.ROOT_URLCONF == "config.urls"
    assert isinstance(settings.DEBUG, bool)
    assert settings.SECRET_KEY
    # Secrets must never default to a committed value.
    assert "django-insecure" not in settings.SECRET_KEY


def test_database_is_postgres():
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"


@pytest.mark.django_db
def test_database_connectivity():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
