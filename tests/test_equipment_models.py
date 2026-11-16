import os
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from google.cloud.ndb import model as ndb_model
from google.cloud.ndb.exceptions import BadValueError

from db import equipment
from db.equipment import CheckoutEntry, Equipment

CHICAGO_TZ = ZoneInfo("America/Chicago")


class EquipmentModelValidationTest(unittest.TestCase):
    def setUp(self):
        self.context = equipment.client.context()
        self.context.__enter__()

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_defaults(self):
        item = Equipment(id="IMC-00001", name="Canon R6")
        self.assertEqual(item.barcode_id, "IMC-00001")
        self.assertEqual(item.status, "available")
        self.assertFalse(item.is_kit)
        self.assertEqual(item.kit_contents, [])
        self.assertEqual(item.history, [])

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(BadValueError):
            Equipment(id="IMC-00002", name="Mic", status="lost")

    def test_negative_money_is_rejected(self):
        with self.assertRaises(ValueError):
            Equipment(id="IMC-00003", name="Mic", value=-1.0)
        with self.assertRaises(ValueError):
            Equipment(id="IMC-00004", name="Mic", replacement_cost=-5.0)

    # ndb checks required fields when converting to a Datastore entity (on
    # put), so call that conversion directly to test without the emulator
    def test_name_is_required_on_save(self):
        with self.assertRaises(BadValueError):
            ndb_model._entity_to_ds_entity(Equipment(id="IMC-00005"))

    def test_checkout_entry_requires_borrower_on_save(self):
        entry = CheckoutEntry(
            borrower_email="a@illinimedia.com",
            checked_out_at=datetime.now(CHICAGO_TZ),
            checked_out_by="ops@illinimedia.com",
        )
        item = Equipment(id="IMC-00006", name="Mic", history=[entry])
        with self.assertRaises(BadValueError):
            ndb_model._entity_to_ds_entity(item)


@unittest.skipUnless(
    os.environ.get("DATASTORE_EMULATOR_HOST"), "Datastore emulator not running"
)
class EquipmentModelRoundTripTest(unittest.TestCase):
    def test_saves_and_loads_kit_with_history(self):
        checked_out_at = datetime(2026, 11, 16, 14, 30, tzinfo=CHICAGO_TZ)
        with equipment.client.context():
            Equipment(
                id="IMC-TEST-ROUNDTRIP",
                name="Podcast kit",
                is_kit=True,
                kit_contents=["Zoom H6", "2x SM58", "XLR cables"],
                value=850.0,
                purchase_date=date(2025, 8, 20),
                purchase_location="B&H",
                status="checked_out",
                history=[
                    CheckoutEntry(
                        borrower_name="Jane Doe",
                        borrower_email="jdoe@illinimedia.com",
                        checked_out_at=checked_out_at,
                        checked_out_by="ops@illinimedia.com",
                    )
                ],
                updated_by="ops@illinimedia.com",
            ).put()

        with equipment.client.context():
            item = Equipment.get_by_id("IMC-TEST-ROUNDTRIP", use_cache=False)
            try:
                self.assertEqual(item.barcode_id, "IMC-TEST-ROUNDTRIP")
                self.assertEqual(
                    item.kit_contents, ["Zoom H6", "2x SM58", "XLR cables"]
                )
                self.assertEqual(item.purchase_date, date(2025, 8, 20))
                self.assertEqual(len(item.history), 1)
                entry = item.history[-1]
                self.assertEqual(entry.borrower_name, "Jane Doe")
                self.assertEqual(entry.checked_out_at, checked_out_at)
                self.assertIsNone(entry.returned_at)
                self.assertIsNotNone(item.created_at)
            finally:
                item.key.delete()


if __name__ == "__main__":
    unittest.main()
