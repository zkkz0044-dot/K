import unittest
from kk_k.world_observer import observe, TOPICS

class WorldObserverTests(unittest.TestCase):
 def test_exact_five_topics_and_search_only(self):
  seen=[]
  def fake(req):
   seen.append(req)
   return {'schema':'K.EXTERNAL.TOOL.RECEIPT.1','tool':'browser.search','risk':'L0','human_required':False,'executed':True,'verified':True,'verdict':'PASS','fk_tool_receipt':{}}
  d=observe(executor=fake)
  self.assertEqual(d['schema'],'K.WORLD.OBSERVATION.BATCH.1')
  self.assertEqual(d['authority'],'EVIDENCE_ONLY')
  self.assertEqual([x['topic'] for x in d['topics']],[x[0] for x in TOPICS])
  self.assertEqual(len(seen),5)
  self.assertTrue(all(r['tool']=='browser.search' and set(r)=={'schema','tool','args'} for r in seen))
 def test_failure_becomes_veto_not_exception(self):
  d=observe(executor=lambda req: (_ for _ in ()).throw(RuntimeError('x')))
  self.assertTrue(all(x['verdict']=='VETO' and x['receipt'] is None for x in d['topics']))
