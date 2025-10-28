import hashlib
from pathlib import Path

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def _legacy_base_path():
    cache_dir = getattr(settings, "HANSARD_CACHE_DIR", None)
    if cache_dir:
        return Path(cache_dir)
    return Path(settings.MEDIA_ROOT) / "document_cache"


def _legacy_xml_path(document, language):
    base = _legacy_base_path()
    if document.document_type == "D":
        if not document.number:
            return None
        return (
            base
            / "debates"
            / str(document.session_id)
            / f"{document.session_id}-{document.number}-{language}.xml"
        )
    if document.document_type == "E":
        if not document.date:
            return None
        return (
            base
            / "evidence"
            / str(document.date.year)
            / str(document.date.month)
            / f"{document.source_id}-{language}.xml"
        )
    return None


def migrate_filesystem_cache(apps, schema_editor):
    Document = apps.get_model("hansards", "Document")
    DocumentXml = apps.get_model("hansards", "DocumentXml")

    qs = Document.objects.filter(downloaded=True).order_by("pk")
    for document in qs.iterator(chunk_size=200):
        record, created = DocumentXml.objects.get_or_create(document=document)
        if record.xml_en and record.xml_fr:
            continue

        path_en = _legacy_xml_path(document, "en")
        path_fr = _legacy_xml_path(document, "fr")
        if not path_en or not path_en.exists() or not path_fr or not path_fr.exists():
            continue

        xml_en = path_en.read_bytes()
        xml_fr = path_fr.read_bytes()
        record.xml_en = xml_en
        record.xml_fr = xml_fr
        record.checksum_en = hashlib.sha256(xml_en).hexdigest()
        record.checksum_fr = hashlib.sha256(xml_fr).hexdigest()
        record.source_url_en = document.xml_source_url or ""
        if record.source_url_en and "-E." in record.source_url_en:
            record.source_url_fr = record.source_url_en.replace("-E.", "-F.")
        else:
            record.source_url_fr = record.source_url_en
        record.last_verified_at = timezone.now()
        record.save()


def rollback_filesystem_cache(apps, schema_editor):
    DocumentXml = apps.get_model("hansards", "DocumentXml")
    DocumentXml.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hansards", "0005_add_bill_stage"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentXml",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "xml_en",
                    models.BinaryField(blank=True, null=True),
                ),
                (
                    "xml_fr",
                    models.BinaryField(blank=True, null=True),
                ),
                (
                    "checksum_en",
                    models.CharField(blank=True, max_length=64),
                ),
                (
                    "checksum_fr",
                    models.CharField(blank=True, max_length=64),
                ),
                (
                    "source_url_en",
                    models.URLField(blank=True),
                ),
                (
                    "source_url_fr",
                    models.URLField(blank=True),
                ),
                (
                    "last_verified_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "document",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="xml_blob",
                        to="hansards.document",
                    ),
                ),
            ],
        ),
        migrations.RunPython(migrate_filesystem_cache, rollback_filesystem_cache),
    ]
