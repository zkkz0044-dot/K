import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

class FP05SystemdDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.unit = (ROOT / "deploy" / "kk-f.service").read_text()
        self.install = (ROOT / "deploy" / "install_layout.sh").read_text()

    def test_service_is_nonroot(self):
        self.assertIn("User=kk-f", self.unit)
        self.assertIn("Group=kk-f", self.unit)
        self.assertNotIn("User=root", self.unit)

    def test_systemd_hardening_present(self):
        for directive in [
            "NoNewPrivileges=yes", "PrivateTmp=yes", "ProtectSystem=strict",
            "ProtectHome=yes", "ProtectKernelTunables=yes", "ProtectKernelModules=yes",
            "ProtectControlGroups=yes", "RestrictSUIDSGID=yes", "LockPersonality=yes",
            "UMask=0077",
        ]:
            self.assertIn(directive, self.unit)

    def test_mutable_paths_are_explicit(self):
        self.assertIn("ReadWritePaths=/var/lib/kk-f /run/kk-f", self.unit)
        self.assertIn("ReadOnlyPaths=/etc/kk-f /opt/kk-f", self.unit)

    def test_authority_and_config_are_root_owned_readable_not_writable(self):
        self.assertIn('install -o root -g root -m 0644 "$AUTHORITY_SOURCE" /etc/kk-f/authority.json', self.install)
        self.assertIn('install -o root -g root -m 0644 "$RUNTIME_SOURCE" /etc/kk-f/runtime.json', self.install)

    def test_runtime_dirs_are_service_owned_private(self):
        self.assertIn("install -d -o kk-f -g kk-f -m 0700 /var/lib/kk-f /run/kk-f", self.install)

    def test_installer_provisions_dedicated_service_identity(self):
        self.assertIn("groupadd --system kk-f", self.install)
        self.assertIn("useradd --system --gid kk-f", self.install)
        self.assertIn("--shell /usr/sbin/nologin kk-f", self.install)

    def test_installer_places_root_owned_code_snapshot(self):
        self.assertIn("cp -a src/kk_f /opt/kk-f/src/kk_f.new", self.install)
        self.assertIn("chown -R root:root /opt/kk-f/src/kk_f.new", self.install)
        self.assertIn("mv /opt/kk-f/src/kk_f.new /opt/kk-f/src/kk_f", self.install)

    def test_no_external_runtime_dependency_in_unit(self):
        lowered = self.unit.lower()
        for forbidden in ["github", "exampleprovider", "codex", "supabase", "ssh", "desktop commander", "bridge"]:
            self.assertNotIn(forbidden, lowered)

if __name__ == "__main__":
    unittest.main()
