#coding=utf8

"""
scrapy扩展
"""

from scrapy import signals
from scrapy.exceptions import NotConfigured

class SpiderRequestLogging(object):

    def __init__(self, crawler):
        self.num_item_scraped = 0
        self.num_request_scheduled = 0
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        # first check if the extension should be enabled and raise
        # NotConfigured otherwise
        if not crawler.settings.getbool('MYEXT_ENABLED'):
            raise NotConfigured
            
        # instantiate the extension object
        ext = cls(crawler)
        
        # connect the extension object to signals
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.request_scheduled, signal=signals.request_scheduled)
        
        # return the extension object
        return ext

    def item_scraped(self, item, spider):
        self.num_item_scraped += 1
            
    def request_scheduled(self, request, spider):
        # request被发出
        self.num_request_scheduled += 1
