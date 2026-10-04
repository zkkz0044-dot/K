import unittest
from kk_k.database_readonly import (
    DatabaseReadError, backend_unavailable_receipt,
    parse_request, reject_raw_sql,
)

class DatabaseReadonlyTests(unittest.TestCase):
    def test_exact_named_view_request(self):
        r=parse_request({
            'schema':'K.DB.READ.REQUEST.1',
            'dataset':'orders',
            'view':'recent',
            'filters':{'status':'paid','min_total':100},
            'limit':20,
        })
        self.assertEqual(r.dataset,'orders')
        self.assertEqual(r.limit,20)

    def test_raw_sql_is_forbidden(self):
        with self.assertRaises(DatabaseReadError): reject_raw_sql('SELECT * FROM x')
        with self.assertRaises(DatabaseReadError): reject_raw_sql({'sql':'SELECT 1'})

    def test_extra_fields_fail_closed(self):
        with self.assertRaises(DatabaseReadError):
            parse_request({'schema':'K.DB.READ.REQUEST.1','dataset':'x','view':'y','filters':{},'limit':1,'sql':'SELECT 1'})

    def test_limit_and_filter_bounds(self):
        for bad in (0,101,True):
            with self.assertRaises(DatabaseReadError):
                parse_request({'schema':'K.DB.READ.REQUEST.1','dataset':'x','view':'y','filters':{},'limit':bad})
        with self.assertRaises(DatabaseReadError):
            parse_request({'schema':'K.DB.READ.REQUEST.1','dataset':'x','view':'y','filters':{'a':'x'*201},'limit':1})

    def test_unbound_backend_veto(self):
        r=parse_request({'schema':'K.DB.READ.REQUEST.1','dataset':'orders','view':'recent','filters':{},'limit':10})
        out=backend_unavailable_receipt(r)
        self.assertEqual(out['status'],'VETO')
        self.assertEqual(out['reason_code'],'DATABASE_BACKEND_UNBOUND')
        self.assertEqual(out['rows'],[])

if __name__=='__main__':
    unittest.main()
