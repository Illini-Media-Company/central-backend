"""
CRUD and checkout tests for db/equipment.py. These need the Datastore emulator:

    gcloud beta emulators datastore start --consistency=1.0
    $(gcloud beta emulators datastore env-init)
    python -m unittest tests.test_equipment_crud -v

--consistency=1.0 matters: by default the emulator returns stale query results
10% of the time to imitate old Datastore, which makes the list test flaky.
Production (Firestore in Datastore mode) queries are strongly consistent.

Tests only touch barcode IDs they create and delete them afterwards, so they
are safe to run against your normal dev emulator.
"""

import os
import threading
import unittest
from datetime import date, datetime

from db import equipment
from db.equipment import (
    AlreadyCheckedOut,
    DuplicateBarcodeId,
    Equipment,
    EquipmentNotFound,
    EquipmentRetired,
    NotCheckedOut,
    check_out_equipment,
    create_equipment,
    get_equipment,
    list_equipment,
    restore_equipment,
    retire_equipment,
    return_equipment,
    update_equipment,
)

OPS = "ops@illinimedia.com"


@unittest.skipUnless(
    os.environ.get("DATASTORE_EMULATOR_HOST"), "Datastore emulator not running"
)
class EquipmentCrudTest(unittest.TestCase):
    def setUp(self):
        self.created = []

    def tearDown(self):
        with equipment.client.context():
            for barcode_id in self.created:
                equipment.ndb.Key(Equipment, barcode_id).delete()

    def make(self, barcode_id="TEST-0001", **fields):
        fields.setdefault("name", "Canon R6")
        item = create_equipment(OPS, barcode_id=barcode_id, **fields)
        self.created.append(item.barcode_id)
        return item

    # ——— Create ———

    def test_create_with_existing_label(self):
        item = self.make(
            " TEST-0001 ",
            value=2499.0,
            purchase_date=date(2025, 8, 20),
            purchase_location="B&H",
        )
        self.assertEqual(item.barcode_id, "TEST-0001")  # whitespace trimmed
        self.assertEqual(item.status, "available")
        self.assertEqual(item.updated_by, OPS)
        self.assertEqual(get_equipment("TEST-0001").purchase_location, "B&H")

    def test_create_refuses_duplicate_barcode_id(self):
        self.make("TEST-0001")
        with self.assertRaises(DuplicateBarcodeId):
            create_equipment(OPS, barcode_id="TEST-0001", name="Other camera")
        self.assertEqual(get_equipment("TEST-0001").name, "Canon R6")

    def test_create_generates_barcode_id(self):
        item = create_equipment(OPS, name="Tripod")
        self.created.append(item.barcode_id)
        self.assertRegex(item.barcode_id, r"^IMC-\d{5}$")
        self.assertIsNotNone(get_equipment(item.barcode_id))

    def test_create_rejects_missing_name_and_protected_fields(self):
        with self.assertRaises(ValueError):
            create_equipment(OPS, barcode_id="TEST-0002", name="  ")
        with self.assertRaises(ValueError):
            create_equipment(
                OPS, barcode_id="TEST-0002", name="Mic", status="checked_out"
            )
        self.assertIsNone(get_equipment("TEST-0002"))

    # ——— Read ———

    def test_list_hides_retired_and_sorts_by_name(self):
        self.make("TEST-0001", name="zoom recorder")
        self.make("TEST-0002", name="Audio kit")
        self.make("TEST-0003", name="Broken light")
        retire_equipment("TEST-0003", OPS)

        names = [i.name for i in list_equipment() if i.barcode_id.startswith("TEST-")]
        self.assertEqual(names, ["Audio kit", "zoom recorder"])

        all_ids = {i.barcode_id for i in list_equipment(include_retired=True)}
        self.assertIn("TEST-0003", all_ids)

    def test_get_missing_returns_none(self):
        self.assertIsNone(get_equipment("TEST-MISSING"))

    # ——— Update ———

    def test_update_details(self):
        self.make("TEST-0001")
        item = update_equipment(
            "TEST-0001",
            "other@illinimedia.com",
            name="Canon R6 Mark II",
            is_kit=True,
            kit_contents=["Body", "Battery"],
        )
        self.assertEqual(item.name, "Canon R6 Mark II")
        self.assertEqual(item.kit_contents, ["Body", "Battery"])
        self.assertEqual(item.updated_by, "other@illinimedia.com")

    def test_update_cannot_change_status_or_history(self):
        self.make("TEST-0001")
        for field in ("status", "history", "created_at"):
            with self.assertRaises(ValueError):
                update_equipment("TEST-0001", OPS, **{field: "x"})
        # barcode_id is the function's own argument, so Python blocks it
        with self.assertRaises(TypeError):
            update_equipment("TEST-0001", OPS, **{"barcode_id": "TEST-9999"})

    def test_update_missing_item(self):
        with self.assertRaises(EquipmentNotFound):
            update_equipment("TEST-MISSING", OPS, name="x")

    # ——— Check out / return ———

    def test_check_out_and_return(self):
        self.make("TEST-0001")
        item = check_out_equipment("TEST-0001", "Jane Doe", "jdoe@illinimedia.com", OPS)
        self.assertEqual(item.status, "checked_out")
        self.assertEqual(item.last_entry.borrower_name, "Jane Doe")
        self.assertIsNone(item.last_entry.returned_at)

        item = return_equipment("TEST-0001", "intern@illinimedia.com")
        self.assertEqual(item.status, "available")
        self.assertEqual(item.last_entry.returned_by, "intern@illinimedia.com")
        self.assertIsNotNone(item.last_entry.returned_at)

        # Most recent borrower is still shown after return
        saved = get_equipment("TEST-0001")
        self.assertEqual(len(saved.history), 1)
        self.assertEqual(saved.to_dict()["borrower"]["name"], "Jane Doe")

    def test_second_checkout_is_refused_with_current_borrower(self):
        self.make("TEST-0001")
        check_out_equipment("TEST-0001", "Jane Doe", "jdoe@illinimedia.com", OPS)
        with self.assertRaises(AlreadyCheckedOut) as caught:
            check_out_equipment("TEST-0001", "Sam Lee", "slee@illinimedia.com", OPS)
        self.assertEqual(caught.exception.borrower_name, "Jane Doe")
        self.assertEqual(len(get_equipment("TEST-0001").history), 1)

    def test_return_when_not_checked_out_is_refused(self):
        self.make("TEST-0001")
        with self.assertRaises(NotCheckedOut):
            return_equipment("TEST-0001", OPS)
        self.assertEqual(get_equipment("TEST-0001").history, [])

    def test_check_out_missing_item(self):
        with self.assertRaises(EquipmentNotFound):
            check_out_equipment("TEST-MISSING", "Jane", "j@illinimedia.com", OPS)

    def test_two_people_checking_out_at_once(self):
        self.make("TEST-0001")
        results = []
        start = threading.Barrier(2)

        def attempt(name):
            start.wait()
            try:
                check_out_equipment("TEST-0001", name, f"{name}@illinimedia.com", OPS)
                results.append("ok")
            except AlreadyCheckedOut:
                results.append("refused")

        threads = [threading.Thread(target=attempt, args=(n,)) for n in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(results), ["ok", "refused"])
        self.assertEqual(len(get_equipment("TEST-0001").history), 1)

    # ——— Retire / restore ———

    def test_retire_and_restore(self):
        self.make("TEST-0001")
        self.assertEqual(retire_equipment("TEST-0001", OPS).status, "retired")
        with self.assertRaises(EquipmentRetired):
            check_out_equipment("TEST-0001", "Jane", "j@illinimedia.com", OPS)
        self.assertEqual(restore_equipment("TEST-0001", OPS).status, "available")

    def test_cannot_retire_checked_out_item(self):
        self.make("TEST-0001")
        check_out_equipment("TEST-0001", "Jane Doe", "jdoe@illinimedia.com", OPS)
        with self.assertRaises(AlreadyCheckedOut):
            retire_equipment("TEST-0001", OPS)
        self.assertEqual(get_equipment("TEST-0001").status, "checked_out")

    # ——— to_dict ———

    def test_to_dict_keeps_native_dates(self):
        self.make("TEST-0001", purchase_date=date(2025, 8, 20), value=10.5)
        data = get_equipment("TEST-0001").to_dict()
        self.assertEqual(data["barcode_id"], "TEST-0001")
        self.assertEqual(data["purchase_date"], date(2025, 8, 20))
        self.assertIsInstance(data["created_at"], datetime)
        self.assertIsNone(data["borrower"])
        self.assertIsNone(data["checked_out_at"])
        self.assertEqual(data["history"], [])

        check_out_equipment("TEST-0001", "Jane Doe", "jdoe@illinimedia.com", OPS)
        data = get_equipment("TEST-0001").to_dict()
        self.assertEqual(
            data["borrower"], {"name": "Jane Doe", "email": "jdoe@illinimedia.com"}
        )
        self.assertIsInstance(data["checked_out_at"], datetime)
        self.assertIsNotNone(data["checked_out_at"].tzinfo)  # timezone-aware
        self.assertIsNone(data["returned_at"])
        self.assertEqual(len(data["history"]), 1)
        self.assertIsInstance(data["history"][0]["checked_out_at"], datetime)


if __name__ == "__main__":
    unittest.main()
