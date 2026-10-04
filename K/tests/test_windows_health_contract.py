import unittest
from kk_k.windows_health_contract import WindowsHealthError, parse_request, verify_receipt

class WindowsHealthContractTests(unittest.TestCase):
    def test_exact_request(self):
        self.assertEqual(parse_request({'schema':'K.WINDOWS.HEALTH.REQUEST.1','host':'win-main'}),'win-main')

    def test_request_rejects_extra_fields(self):
        with self.assertRaises(WindowsHealthError):
            parse_request({'schema':'K.WINDOWS.HEALTH.REQUEST.1','host':'win-main','command':'whoami'})

    def test_valid_receipt(self):
        data={
            'os':'windows','hostname':'DESKTOP-TEST','uptime_seconds':10,'cpu_percent':12.5,
            'memory':{'total_bytes':100,'free_bytes':40},
            'disk_system':{'total_bytes':200,'free_bytes':50},
            'agent':{'protocol':'KK.WINDOWS.HEALTH.1','version':'1','read_only':True},
        }
        out=verify_receipt({'schema':'K.WINDOWS.HEALTH.RECEIPT.1','host':'win-main','status':'PASS','data':data})
        self.assertEqual(out['os'],'windows')

    def test_agent_must_be_read_only(self):
        data={'os':'windows','hostname':'X','uptime_seconds':1,'cpu_percent':1,'memory':{'total_bytes':1,'free_bytes':1},'disk_system':{'total_bytes':1,'free_bytes':1},'agent':{'protocol':'KK.WINDOWS.HEALTH.1','version':'1','read_only':False}}
        with self.assertRaises(WindowsHealthError):
            verify_receipt({'schema':'K.WINDOWS.HEALTH.RECEIPT.1','host':'x','status':'PASS','data':data})

if __name__=='__main__': unittest.main()
