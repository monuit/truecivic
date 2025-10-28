from __future__ import annotations

import datetime

from django.test import TestCase

from parliament.api.v1.services import BillDetailPayloadBuilder
from parliament.bills.models import Bill
from parliament.core.models import Session
from parliament.rag.models import KnowledgeSource


# MARK: Bill detail payload builder tests


class BillDetailPayloadBuilderTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.session = Session.objects.create(
            id="99-1",
            name="99th Parliament, 1st Session",
            start=datetime.date(2020, 1, 1),
            parliamentnum=99,
            sessnum=1,
        )
        self.bill_with_legisinfo = Bill.objects.create(
            number="C-1",
            number_only=1,
            institution="C",
            session=self.session,
            status_code="Introduced",
            name_en="A Bill With LEGISinfo",
            short_title_en="Test Bill",
            legisinfo_id=12345,
        )
        self.bill_without_legisinfo = Bill.objects.create(
            number="C-2",
            number_only=2,
            institution="C",
            session=self.session,
            status_code="Introduced",
            name_en="A Bill Without LEGISinfo",
            short_title_en="Fallback Bill",
        )

    def test_rag_scope_uses_legisinfo_identifier(self) -> None:
        builder = BillDetailPayloadBuilder(
            session_id=self.session.id,
            bill_number=self.bill_with_legisinfo.number,
        )

        payload = builder._serialize_bill(self.bill_with_legisinfo)
        scope = payload["rag_scope"]

        self.assertIsNotNone(scope)
        self.assertEqual(scope["source_type"], KnowledgeSource.BILL)
        self.assertEqual(scope["source_identifier"], "bill:12345")

    def test_rag_scope_falls_back_to_bill_primary_key(self) -> None:
        builder = BillDetailPayloadBuilder(
            session_id=self.session.id,
            bill_number=self.bill_without_legisinfo.number,
        )

        payload = builder._serialize_bill(self.bill_without_legisinfo)
        scope = payload["rag_scope"]

        self.assertIsNotNone(scope)
        self.assertEqual(scope["source_type"], KnowledgeSource.BILL)
        self.assertEqual(scope["source_identifier"],
                         f"bill:{self.bill_without_legisinfo.id}")

    def test_rag_scope_absent_when_bill_has_no_identifier(self) -> None:
        builder = BillDetailPayloadBuilder(
            session_id=self.session.id,
            bill_number=self.bill_with_legisinfo.number,
        )

        unsaved_bill = Bill(
            number="C-3",
            number_only=3,
            institution="C",
            session=self.session,
            status_code="Introduced",
            name_en="Unsaved bill",
            short_title_en="Unsaved",
        )

        payload = builder._serialize_bill(unsaved_bill)

        self.assertIsNone(payload["rag_scope"])
