"""media_store

A write-through database store for uploaded media (product / profile images).

Rationale: ``backend/media`` lives on an ephemeral local disk and is gitignored,
so image files vanish on a Render redeploy or when the Postgres database is
copied between machines while the files stay behind — every ``/media/...`` URL
then 404s and posted pictures stop showing.

This app stores the same bytes in a Postgres table. The custom storage keeps
the filesystem behaviour (files are still written to ``MEDIA_ROOT``) and, as a
fallback reader, serves them back from the database when the disk copy is gone.
``/media/...`` URLs and the API contract are unchanged.
"""
