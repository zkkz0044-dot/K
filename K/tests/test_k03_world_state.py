import unittest

from kk_k.world_state import WorldStateError, build_snapshot, lookup


def fact(key="f.status", value="ACCEPTED", source="F", observed=100, ttl=10):
    return {"schema":"K03.FACT.1","key":key,"value":value,"source_id":source,"observed_at":observed,"ttl_seconds":ttl}


class WorldStateTests(unittest.TestCase):
    def test_fresh_known_with_provenance(self):
        snap = build_snapshot([fact()], 110)
        got = lookup(snap, "f.status")
        self.assertEqual(got["state"], "KNOWN")
        self.assertEqual(got["source_id"], "F")

    def test_stale_is_not_known(self):
        snap = build_snapshot([fact()], 111)
        self.assertEqual(lookup(snap, "f.status")["state"], "STALE")

    def test_missing_is_unknown(self):
        snap = build_snapshot([], 100)
        self.assertEqual(lookup(snap, "f.status"), {"state":"UNKNOWN"})

    def test_duplicate_key_rejected(self):
        with self.assertRaises(WorldStateError): build_snapshot([fact(), fact(source="other")], 100)

    def test_extra_field_rejected(self):
        bad = fact(); bad["extra"] = 1
        with self.assertRaises(WorldStateError): build_snapshot([bad], 100)

    def test_bad_time_type_rejected(self):
        with self.assertRaises(WorldStateError): build_snapshot([fact(observed=True)], 100)

    def test_bad_ttl_rejected(self):
        with self.assertRaises(WorldStateError): build_snapshot([fact(ttl=999999999)], 100)

    def test_bad_key_rejected(self):
        with self.assertRaises(WorldStateError): build_snapshot([fact(key="../x")], 100)

    def test_bad_source_rejected(self):
        with self.assertRaises(WorldStateError): build_snapshot([fact(source="")], 100)

    def test_value_bound(self):
        with self.assertRaises(WorldStateError): build_snapshot([fact(value="x"*1025)], 100)

    def test_snapshot_sorted_deterministically(self):
        snap = build_snapshot([fact(key="z.k"), fact(key="a.k")], 100)
        self.assertEqual([x["key"] for x in snap["facts"]], ["a.k","z.k"])

    def test_lookup_rejects_tampered_snapshot_fact(self):
        snap = build_snapshot([fact()], 100)
        snap["facts"][0]["extra"] = 1
        with self.assertRaises(WorldStateError): lookup(snap, "f.status")

if __name__ == "__main__":
    unittest.main()
