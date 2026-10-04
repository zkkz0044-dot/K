import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.contracts import ContractError, validate_message


BASE = {
    "protocol_version": "0.1",
    "message_id": "123e4567-e89b-42d3-a456-426614174000",
    "kind": "heartbeat",
    "source_role": "worker",
    "target_role": "supervisor",
    "timestamp": "2026-09-03T19:15:00Z",
    "status": "HEALTHY",
    "payload": {},
    "error": None,
}


class F01ContractTests(unittest.TestCase):
    def test_valid_message_passes_and_identity_preserved(self):
        msg = copy.deepcopy(BASE)
        self.assertIs(validate_message(msg), msg)

    def assert_rejected(self, mutate):
        msg = copy.deepcopy(BASE)
        mutate(msg)
        with self.assertRaises(ContractError):
            validate_message(msg)

    def test_unknown_top_level_field_fails_closed(self):
        self.assert_rejected(lambda m: m.__setitem__("surprise", True))

    def test_nonstring_unknown_top_level_field_fails_closed(self):
        self.assert_rejected(lambda m: m.__setitem__(1, True))

    def test_missing_required_field_fails_closed(self):
        self.assert_rejected(lambda m: m.pop("payload"))

    def test_protocol_version_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("protocol_version", "0.2"))

    def test_protocol_version_type_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("protocol_version", 1))

    def test_unknown_role_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("source_role", "brain"))

    def test_role_type_confusion_rejected_as_contract_error(self):
        self.assert_rejected(lambda m: m.__setitem__("source_role", []))

    def test_unknown_kind_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("kind", "arbitrary_shell"))

    def test_kind_type_confusion_rejected_as_contract_error(self):
        self.assert_rejected(lambda m: m.__setitem__("kind", {}))

    def test_unknown_status_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("status", "OK"))

    def test_status_type_confusion_rejected_as_contract_error(self):
        self.assert_rejected(lambda m: m.__setitem__("status", []))

    def test_noncanonical_uuid_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("message_id", m["message_id"].upper()))

    def test_timestamp_without_timezone_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("timestamp", "2026-09-03T19:15:00"))

    def test_timestamp_with_space_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("timestamp", "2026-09-03 19:15:00+00:00"))

    def test_invalid_calendar_timestamp_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("timestamp", "2026-02-30T19:15:00Z"))

    def test_payload_must_be_object(self):
        self.assert_rejected(lambda m: m.__setitem__("payload", []))

    def test_valid_error_object_passes(self):
        msg = copy.deepcopy(BASE)
        msg["kind"] = "fault"
        msg["status"] = "FAILED"
        msg["error"] = {"code": "TIMEOUT", "message": "bounded timeout", "retryable": True, "detail": {}}
        validate_message(msg)

    def test_unknown_error_code_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("error", {"code": "MAGIC", "message": "x", "retryable": False, "detail": {}}))

    def test_error_code_type_confusion_rejected_as_contract_error(self):
        self.assert_rejected(lambda m: m.__setitem__("error", {"code": [], "message": "x", "retryable": False, "detail": {}}))

    def test_unknown_error_field_rejected(self):
        self.assert_rejected(lambda m: m.__setitem__("error", {"code": "TIMEOUT", "message": "x", "retryable": True, "detail": {}, "extra": 1}))

    def test_retryable_must_be_boolean(self):
        self.assert_rejected(lambda m: m.__setitem__("error", {"code": "TIMEOUT", "message": "x", "retryable": 1, "detail": {}}))

    def test_error_detail_must_be_object(self):
        self.assert_rejected(lambda m: m.__setitem__("error", {"code": "TIMEOUT", "message": "x", "retryable": True, "detail": []}))


if __name__ == "__main__":
    unittest.main()
