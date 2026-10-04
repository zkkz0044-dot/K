import json
import tempfile
import unittest
from pathlib import Path

from kk_k.test_support import project_tempdir
from kk_k.constitution import ConstitutionError, EXPECTED, load_constitution


class ConstitutionTests(unittest.TestCase):
    def write(self, text):
        td = project_tempdir()
        path = Path(td.name) / "constitution.json"
        path.write_text(text, encoding="utf-8")
        return td, path

    def test_authoritative_constitution_loads(self):
        value = load_constitution("/root/K/K/K00_CONSTITUTION.json")
        self.assertEqual(value, EXPECTED)

    def test_rejects_extra_field(self):
        bad = dict(EXPECTED); bad["extra"] = True
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_duplicate_key(self):
        raw = '{"schema":"K00.CONSTITUTION.1","schema":"K00.CONSTITUTION.1"}'
        td, path = self.write(raw)
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_weakened_veto(self):
        bad = dict(EXPECTED); bad["k_f_boundary"] = "K_CAN_OVERRIDE_F"
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_mutable_success_rule(self):
        bad = dict(EXPECTED); bad["success_criteria_mutable_after_result"] = True
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_green_channel(self):
        bad = dict(EXPECTED); bad["action_green_channel"] = True
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_arbitrary_execution(self):
        bad = dict(EXPECTED); bad["free_form_execution_authority"] = True
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_wrong_bool_type(self):
        bad = dict(EXPECTED); bad["no_action_legitimate"] = 1
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_external_trust(self):
        bad = dict(EXPECTED); bad["external_inputs_default_trust"] = "TRUSTED"
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_extra_trust_root(self):
        bad = dict(EXPECTED); bad["trusted_roots"] = ["K_INTEGRITY_VERIFIED_CORE", "F", "MODEL"]
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_infallible_self_judgment(self):
        bad = dict(EXPECTED); bad["self_judgment_trust"] = "TRUSTED"
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_trusted_soul_output(self):
        bad = dict(EXPECTED); bad["soul_outputs_trust"] = "TRUSTED"
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_cross_project_access(self):
        bad = dict(EXPECTED); bad["cross_project_access"] = True
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_webroot_staging(self):
        bad = dict(EXPECTED); bad["webroot_staging"] = True
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

    def test_rejects_temp_http_transfer(self):
        bad = dict(EXPECTED); bad["temporary_http_transfer"] = True
        td, path = self.write(json.dumps(bad))
        try:
            with self.assertRaises(ConstitutionError): load_constitution(str(path))
        finally: td.cleanup()

if __name__ == "__main__":
    unittest.main()
