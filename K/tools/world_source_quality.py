#!/usr/bin/env python3
from __future__ import annotations
from urllib.parse import urlparse

NEWSWIRE = ('reuters.com', 'apnews.com')
PRIMARY_FIXED = ('un.org', 'imf.org', 'worldbank.org', 'who.int', 'europa.eu')
COMMUNITY = ('reddit.com', 'zhihu.com', 'quora.com', 'jingyan.baidu.com')
AGGREGATOR = ('msn.com', 'news.google.com')
COMMON_PUBLIC_SUFFIXES = ('co.uk','org.uk','gov.uk','com.au','gov.au','com.cn','gov.cn','co.jp')


def normalize_host(host: str | None) -> str:
    h=(host or '').strip().lower().rstrip('.')
    if h.startswith('www.'):
        h=h[4:]
    return h


def _matches(host: str, base: str) -> bool:
    return host == base or host.endswith('.' + base)


def domain_group(host: str) -> str:
    h=normalize_host(host)
    if not h:
        return 'unknown'
    for base in NEWSWIRE + PRIMARY_FIXED + COMMUNITY + AGGREGATOR:
        if _matches(h, base):
            if base == 'jingyan.baidu.com':
                return 'baidu.com'
            return base
    parts=h.split('.')
    if len(parts) <= 2:
        return h
    for suffix in COMMON_PUBLIC_SUFFIXES:
        if _matches(h, suffix):
            labels=suffix.count('.')+1
            if len(parts) > labels:
                return '.'.join(parts[-(labels+1):])
    return '.'.join(parts[-2:])


def is_government(host: str) -> bool:
    h=normalize_host(host)
    labels=h.split('.') if h else []
    return bool(h.endswith('.gov') or h.endswith('.mil') or 'gov' in labels[-3:])


def classify_source(url: str | None, source_host: str | None = None) -> dict:
    host=normalize_host(source_host)
    if not host and url:
        host=normalize_host(urlparse(url).hostname)
    if is_government(host) or any(_matches(host,x) for x in PRIMARY_FIXED):
        source_class='PRIMARY_OFFICIAL'; priority='HIGH'; lineage='DIRECT_HOST'
    elif any(_matches(host,x) for x in NEWSWIRE):
        source_class='NEWSWIRE'; priority='HIGH'; lineage='DIRECT_HOST'
    elif any(_matches(host,x) for x in COMMUNITY):
        source_class='COMMUNITY'; priority='LOW'; lineage='COMMUNITY_OR_SELF_PUBLISHED'
    elif any(_matches(host,x) for x in AGGREGATOR):
        source_class='AGGREGATOR'; priority='LOW'; lineage='DERIVATIVE_POSSIBLE'
    else:
        source_class='OTHER'; priority='UNRATED'; lineage='UNKNOWN'
    return {
        'retrieval_tool':'browser.search',
        'source_class':source_class,
        'source_priority':priority,
        'independence_group':domain_group(host),
        'lineage_status':lineage,
    }
