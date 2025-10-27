from django.test import SimpleTestCase

from src.services.rag.jurisdiction import JurisdictionSet, normalize_jurisdiction
from src.services.rag.language import normalize_language


class NormalizationTests(SimpleTestCase):
    def test_normalize_jurisdiction_defaults_to_federal(self) -> None:
        self.assertEqual(normalize_jurisdiction(None), "canada-federal")

    def test_normalize_jurisdiction_handles_province_names(self) -> None:
        self.assertEqual(normalize_jurisdiction("Quebec"), "canada-qc")

    def test_jurisdiction_set_deduplicates(self) -> None:
        result = JurisdictionSet.from_env("Canada, ontario, CANADA-ON")
        self.assertEqual(result.choices, ("canada-federal", "canada-on"))

    def test_normalize_language_defaults_to_en(self) -> None:
        self.assertEqual(normalize_language(None), "en")

    def test_normalize_language_handles_variants(self) -> None:
        self.assertEqual(normalize_language("fr-CA"), "fr")
