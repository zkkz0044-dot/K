import importlib.util
from pathlib import Path

MOD=Path('/root/K/K/tools/world_source_quality.py')
spec=importlib.util.spec_from_file_location('world_source_quality',MOD)
wsq=importlib.util.module_from_spec(spec); spec.loader.exec_module(wsq)


def test_newswire_is_high_priority_but_only_a_hint():
    m=wsq.classify_source('https://www.reuters.com/world/x')
    assert m['source_class']=='NEWSWIRE'
    assert m['source_priority']=='HIGH'
    assert m['independence_group']=='reuters.com'
    assert m['lineage_status']=='DIRECT_HOST'


def test_government_is_primary_official():
    m=wsq.classify_source('https://www.cdc.gov/test')
    assert m['source_class']=='PRIMARY_OFFICIAL'
    assert m['source_priority']=='HIGH'
    assert m['independence_group']=='cdc.gov'


def test_community_sources_are_not_high_priority():
    for url,group in [
        ('https://www.reddit.com/r/x','reddit.com'),
        ('https://www.zhihu.com/question/x','zhihu.com'),
        ('https://jingyan.baidu.com/article/x','baidu.com'),
    ]:
        m=wsq.classify_source(url)
        assert m['source_class']=='COMMUNITY'
        assert m['source_priority']=='LOW'
        assert m['independence_group']==group


def test_aggregator_is_derivative_possible():
    m=wsq.classify_source('https://www.msn.com/en-us/news/x')
    assert m['source_class']=='AGGREGATOR'
    assert m['source_priority']=='LOW'
    assert m['lineage_status']=='DERIVATIVE_POSSIBLE'


def test_unknown_source_is_not_silently_downgraded_or_upgraded():
    m=wsq.classify_source('https://sub.example.com/x')
    assert m['source_class']=='OTHER'
    assert m['source_priority']=='UNRATED'
    assert m['independence_group']=='example.com'
    assert m['lineage_status']=='UNKNOWN'
