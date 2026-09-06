from supportops.db import Database
from supportops.seed import seed_database


def test_seed_creates_required_scale_and_demo_records(tmp_path):
    db = Database(tmp_path / "test.db")
    seed_database(db)

    assert db.scalar("SELECT COUNT(*) FROM customers") >= 750
    assert db.scalar("SELECT COUNT(*) FROM orders") >= 3000
    assert db.scalar("SELECT COUNT(*) FROM shipments") >= 3000
    assert db.scalar("SELECT COUNT(*) FROM policies") >= 7
    assert db.one("SELECT id FROM orders WHERE id = ?", ("ORD-10428",))["id"] == "ORD-10428"
    assert db.one("SELECT status FROM shipments WHERE order_id = ?", ("ORD-30991",))["status"] == "lost"


def test_seed_is_idempotent(tmp_path):
    db = Database(tmp_path / "test.db")
    seed_database(db)
    first = db.scalar("SELECT COUNT(*) FROM orders")
    seed_database(db)
    assert db.scalar("SELECT COUNT(*) FROM orders") == first
