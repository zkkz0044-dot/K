import json,tempfile,unittest
from pathlib import Path
from kk_k.world_judge import judge,WorldJudgeError

def fixture(memory=False):
 item={'belief_status':'NOT_EVALUATED','confidence':{'basis':'SINGLE_SEARCH_RESULT_UNCORROBORATED','level':'LOW'},'conflict':{'status':'NOT_CHECKED'},'corroboration':{'independent_sources':1,'status':'NOT_CHECKED'},'evidence_id':'abc12345def67890','evidence_sha256':'a'*64,'memory_eligible':memory,'observed_at':'2026-09-13T05:00:00+00:00','query':'q','snippet':'snippet','source_host':'example.com','source_published_at':None,'status':'OBSERVED_UNVERIFIED','title':'title','topic':'ai_technology','url':'https://example.com/x'}
 return {'schema':'K.WORLD.EVIDENCE.SET.1','observed_at':'2026-09-13T05:00:00+00:00','authority':'EVIDENCE_ONLY','policy':{'observed_is_believed':False,'search_result_is_long_term_memory':False},'items':[item]}

def provider(role,prompt,bad=False):
 prop={'schema':'K.WORLD.JUDGMENT.PROPOSAL.1','assessment':'provisional only','priority_evidence_ids':['bogus000' if bad else 'abc12345def67890'],'noise_evidence_ids':[],'corroborate_evidence_ids':['abc12345def67890'],'follow_up_queries':[{'query':'independent corroboration','reason':'verify independently'}]}
 if role=='WORLD_A': return json.dumps({'schema':'K.WORLD.MODEL.A.1','proposal_text':json.dumps(prop),'confidence':'LOW'})
 if role=='WORLD_B': return json.dumps({'schema':'K.WORLD.MODEL.B.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'})
 return json.dumps({'schema':'K.WORLD.MODEL.C.1','verdict':'APPROVE_A','confidence':'LOW'})

class Tests(unittest.TestCase):
 def runfile(self,d,p):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/'e.json'; f.write_text(json.dumps(d)); return judge(str(f),provider=p)
 def test_approved_stays_provisional(self):
  r=self.runfile(fixture(),provider); self.assertEqual(r['status'],'APPROVED_PROVISIONAL'); self.assertFalse(r['memory_eligible'])
 def test_evidence_memory_escalation_rejected(self):
  with self.assertRaises(WorldJudgeError): self.runfile(fixture(True),provider)
 def test_unknown_evidence_id_rejected(self):
  with self.assertRaises(WorldJudgeError): self.runfile(fixture(),lambda role,prompt:provider(role,prompt,True))

 def test_a_retries_once_after_invalid_candidate(self):
  calls=[]
  def flaky(role,prompt):
   calls.append(role)
   if role=='WORLD_A' and calls.count('WORLD_A')==1:
    bad={'schema':'K.WORLD.JUDGMENT.PROPOSAL.1','assessment':'x','priority_evidence_ids':['unknown000'],'noise_evidence_ids':[],'corroborate_evidence_ids':[],'follow_up_queries':[]}
    return json.dumps({'schema':'K.WORLD.MODEL.A.1','proposal_text':json.dumps(bad),'confidence':'LOW'})
   return provider(role,prompt)
  r=self.runfile(fixture(),flaky)
  self.assertEqual(r['status'],'APPROVED_PROVISIONAL')
  self.assertEqual(calls.count('WORLD_A'),2)

if __name__=='__main__': unittest.main()