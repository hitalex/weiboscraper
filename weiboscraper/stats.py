#coding=utf8

"""
该类用于实现数据收集器，记录spider运行
"""

from scrapy import signals
from scrapy.statscol import MemoryStatsCollector, StatsCollector

class ItemStatsCollector(StatsCollector):

    def __init__(self, stats):
        super(ItemStatsCollector, self).__init__(stats)
        self.stats = stats
        
        #import ipdb; ipdb.set_trace()
        # 初始化统计量
        #self.stats.set_value('items_scraped', 0)
        #self.stats.set_value('request_scheduled', 0) # 记录request被发出的次数

    @classmethod
    def from_crawler(cls, crawler):
        """ Scrapy内部通过调用该类方法来实例化该stats收集器
        在spider中，可以通过self.crawler.stats来查看该实例化的对象
        """
        ext = cls(crawler.stats)
        
        # 添加信号处理
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(ext.request_scheduled, signal=signals.request_scheduled)
        
        return ext
        
    def item_scraped(self, item, spider):
        # item被抓取
        self.stats.inc_value('items_scraped')
        
    def request_scheduled(self, request, spider):
        # request被发出
        self.stats.inc_value('request_scheduled')
