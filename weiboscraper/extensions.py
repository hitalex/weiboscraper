#coding=utf8

"""
scrapy扩展
"""

from scrapy import signals
from scrapy.exceptions import NotConfigured

class SpiderRequestLogging(object):

    def __init__(self):
        self.items_scraped = 0
        self.request_scheduled = 0

    @classmethod
    def from_crawler(cls, crawler):
        # instantiate the extension object
        ext = cls()

        # connect the extension object to signals
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.request_scheduled, signal=signals.request_scheduled)
                
        # return the extension object
        return ext

    def item_scraped(self, item, spider):
        self.items_scraped += 1
            
    def request_scheduled(self, request, spider):
        # request被发出
        self.request_scheduled += 1
