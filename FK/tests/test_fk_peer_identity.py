import unittest

from kk_f.fk_peer_identity import (
    FKPeerIdentityError, authorize_peer, cgroup_contains_unit,
)


class FKPeerIdentityTests(unittest.TestCase):
    def test_exact_unit_component_matches(self):
        text='0::/system.slice/kk-k-runtime.service\n'
        self.assertTrue(cgroup_contains_unit(text,'kk-k-runtime.service'))

    def test_substring_unit_does_not_match(self):
        text='0::/system.slice/not-kk-k-runtime.service-extra\n'
        self.assertFalse(cgroup_contains_unit(text,'kk-k-runtime.service'))

    def test_invalid_unit_rejected(self):
        with self.assertRaises(FKPeerIdentityError):
            cgroup_contains_unit('', '../kk-k-runtime.service')

    def test_uid_mode_is_exact(self):
        self.assertTrue(authorize_peer(pid=1,uid=123,allowed_uid=123))
        self.assertFalse(authorize_peer(pid=1,uid=124,allowed_uid=123))

    def test_cgroup_mode_rejects_root_even_before_membership(self):
        self.assertFalse(authorize_peer(pid=1,uid=0,allowed_cgroup_unit='kk-k-runtime.service'))


if __name__ == '__main__':
    unittest.main()
