import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.process_spec import ProcessSpecError, validate_process_spec

BASE = {
    "version": "0.1",
    "executable": "/opt/kk-f/bin/worker",
    "argv": ["--mode", "serve"],
    "cwd": "/var/lib/kk-f",
    "env": {"KK_F_MODE": "prod", "PATH": "/usr/bin"},
    "sha256": "a" * 64,
}


class F09ProcessSpecTests(unittest.TestCase):
    def test_valid_spec(self):
        self.assertEqual(validate_process_spec(dict(BASE)), BASE)

    def test_unknown_field_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, shell=True))

    def test_missing_field_rejected(self):
        spec = dict(BASE)
        del spec["sha256"]
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(spec)

    def test_relative_executable_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, executable="bin/worker"))

    def test_relative_cwd_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, cwd="var/lib/kk-f"))

    def test_bad_hash_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, sha256="ABC"))

    def test_argv_must_be_list(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, argv="--mode serve"))

    def test_argv_type_confusion_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, argv=[1]))

    def test_argv_nul_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, argv=["ok\x00bad"]))

    def test_env_must_be_object(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, env=[]))

    def test_invalid_env_name_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, env={"BAD-NAME": "x"}))

    def test_env_value_type_confusion_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, env={"GOOD": 1}))

    def test_env_nul_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, env={"GOOD": "x\x00y"}))

    def test_dynamic_loader_environment_rejected(self):
        for key in ("LD_PRELOAD","LD_LIBRARY_PATH","LD_AUDIT","DYLD_INSERT_LIBRARIES"):
            with self.assertRaises(ProcessSpecError, msg=key): validate_process_spec(dict(BASE,env={key:"x"}))

    def test_interpreter_injection_environment_rejected(self):
        for key in ("PYTHONPATH","PYTHONHOME","PYTHONINSPECT","PYTHONSTARTUP","BASH_ENV","NODE_OPTIONS"):
            with self.assertRaises(ProcessSpecError, msg=key): validate_process_spec(dict(BASE,env={key:"x"}))

    def test_unsupported_version_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec(dict(BASE, version="0.2"))

    def test_spec_type_confusion_rejected(self):
        with self.assertRaises(ProcessSpecError):
            validate_process_spec([])
