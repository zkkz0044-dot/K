import unittest
from kk_k.capability_cognition import select_capability, acquire_capability_evidence, capability_context, capability_audit_summary

class CapabilityCognitionTests(unittest.TestCase):
 def test_health_routes_remote(self): self.assertEqual(select_capability('查看VPS当前内存和CPU').tool,'remote.vps.health')
 def test_fresh_routes_search(self): self.assertEqual(select_capability('搜索今天最新ExampleAI消息').tool,'browser.search')
 def test_explicit_project_file_routes_files(self):
  n=select_capability('读取文件 /root/K/K/PROJECT_STATE.json'); self.assertEqual(n.tool,'files.read'); self.assertEqual(n.args['path'],'/root/K/K/PROJECT_STATE.json')
 def test_no_need_does_not_call_tool(self): self.assertIsNone(select_capability('解释一下递归函数'))
 def test_receipt_is_evidence_not_authority(self):
  def fake(req): return {'schema':'K.EXTERNAL.TOOL.RECEIPT.1','tool':req['tool'],'risk':'L0','human_required':False,'executed':True,'verified':True,'verdict':'PASS','fk_tool_receipt':{}}
  e=acquire_capability_evidence('查看VPS健康状态',executor=fake); self.assertEqual(e['verdict'],'PASS'); self.assertNotIn('action_id',e)
 def test_veto_is_preserved(self):
  def fake(req): return {'schema':'K.EXTERNAL.TOOL.RECEIPT.1','tool':req['tool'],'risk':'L0','human_required':False,'executed':False,'verified':False,'verdict':'VETO','fk_tool_receipt':{}}
  self.assertEqual(acquire_capability_evidence('搜索今天最新消息',executor=fake)['verdict'],'VETO')

if __name__=='__main__': unittest.main()

class WorldBootstrapRoutingTests(unittest.TestCase):
 def test_geography_uses_foundation(self):
  n=select_capability('国家和时区是什么关系'); self.assertEqual(n.tool,'files.read'); self.assertTrue(n.args['path'].endswith('01_geography.md'))
 def test_society_uses_foundation(self):
  n=select_capability('政府、法院和企业是什么关系'); self.assertTrue(n.args['path'].endswith('03_society.md'))
 def test_evidence_uses_foundation(self):
  n=select_capability('证据和事实有什么区别'); self.assertTrue(n.args['path'].endswith('10_evidence_reasoning.md'))
 def test_freshness_beats_foundation(self):
  n=select_capability('搜索今天最新的国家领导人'); self.assertEqual(n.tool,'browser.search')

class WorldBootstrapV02RoutingTests(unittest.TestCase):
 def test_history_uses_foundation(self):
  n=select_capability('历史研究为什么要区分事件时间和记录时间'); self.assertTrue(n.args['path'].endswith('02_history.md'))
 def test_economics_uses_foundation(self):
  n=select_capability('经济学里收入、财富和利润有什么区别'); self.assertTrue(n.args['path'].endswith('04_economics.md'))
 def test_science_uses_foundation(self):
  n=select_capability('科学实验为什么相关性不能直接证明因果关系'); self.assertTrue(n.args['path'].endswith('05_science.md'))
 def test_current_economics_uses_search(self):
  n=select_capability('今天最新的美国利率是多少'); self.assertEqual(n.tool,'browser.search')
 def test_current_science_uses_search(self):
  n=select_capability('搜索最新科学研究结果'); self.assertEqual(n.tool,'browser.search')

class WorldBootstrapV03RoutingTests(unittest.TestCase):
 def test_engineering_uses_foundation(self):
  n=select_capability('工程设计为什么需要验证和验收'); self.assertTrue(n.args['path'].endswith('06_engineering.md'))
 def test_computing_uses_foundation(self):
  n=select_capability('计算机网络里认证和授权有什么区别'); self.assertTrue(n.args['path'].endswith('07_computing.md'))
 def test_biology_uses_foundation(self):
  n=select_capability('生物进化为什么不是朝着完美发展'); self.assertTrue(n.args['path'].endswith('08_biology_life.md'))
 def test_human_behavior_uses_foundation(self):
  n=select_capability('人类行为中的信任和沟通有什么关系'); self.assertTrue(n.args['path'].endswith('09_human_behavior.md'))
 def test_current_software_uses_search(self):
  n=select_capability('搜索最新Linux内核版本'); self.assertEqual(n.tool,'browser.search')
 def test_current_biology_uses_search(self):
  n=select_capability('今天最新的生物研究新闻'); self.assertEqual(n.tool,'browser.search')

class WorldSnapshotV01RoutingTests(unittest.TestCase):
 def test_2026_world_orientation_uses_snapshot(self):
  n=select_capability('给我2026年的世界背景'); self.assertEqual(n.tool,'files.read'); self.assertTrue(n.args['path'].endswith('2026-09-06_world_snapshot.md'))
 def test_explicit_snapshot_uses_snapshot(self):
  n=select_capability('读取世界快照作为背景'); self.assertTrue(n.args['path'].endswith('2026-09-06_world_snapshot.md'))
 def test_current_world_forces_search(self):
  n=select_capability('当前世界背景有什么变化'); self.assertEqual(n.tool,'browser.search')
 def test_latest_world_forces_search(self):
  n=select_capability('搜索最新世界局势'); self.assertEqual(n.tool,'browser.search')

class WorldObservationRoutingTests(unittest.TestCase):
 def test_recent_observation_uses_latest_archive(self):
  n=select_capability('K最近观察到了什么'); self.assertEqual(n.tool,'files.read'); self.assertTrue(n.args['path'].endswith('/world/observations/latest.md'))
 def test_current_world_still_forces_search(self):
  n=select_capability('当前世界观察有什么变化'); self.assertEqual(n.tool,'browser.search')

class CapabilityAuditSummaryTests(unittest.TestCase):
 def test_oversize_context_gets_compact_audit_summary(self):
  evidence={
   "schema":"K.COGNITION.CAPABILITY_EVIDENCE.1","tool":"files.read","reason":"WORLD_EVIDENCE_FOUNDATION","verdict":"PASS",
   "receipt":{"verified":True,"executed":True,"fk_tool_receipt":{"verdict":"PASS"},"payload":"x"*3000}
  }
  full=capability_context(evidence); audit=capability_audit_summary(evidence)
  self.assertGreater(len(full.encode("utf-8")),2048)
  self.assertLessEqual(len(audit.encode("utf-8")),2048)
  self.assertIn("receipt_sha256",audit)

 def test_small_context_is_preserved_exactly(self):
  evidence={"schema":"K.COGNITION.CAPABILITY_EVIDENCE.1","tool":"files.read","reason":"R","verdict":"VETO","receipt":{}}
  self.assertEqual(capability_audit_summary(evidence),capability_context(evidence))

class CurrentWorldModelRoutingTests(unittest.TestCase):
 def test_explicit_k_world_model_reads_derived_view(self):
  n=select_capability('K现在怎么看世界，读取当前世界模型')
  self.assertEqual(n.tool,'files.read')
  self.assertTrue(n.args['path'].endswith('/world/current_model/current.md'))
 def test_fresh_world_question_still_searches(self):
  n=select_capability('现在世界发生了什么最新变化')
  self.assertEqual(n.tool,'browser.search')
