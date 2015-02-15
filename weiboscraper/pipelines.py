# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

from scrapy import log
from scrapy.exceptions import DropItem

class WeiboscraperPipeline(object):
    def process_item(self, item, spider):
        return item
        
class UserInfoPipeline(object):
    """ 用于处理用户信息的pipeline
    
    NOTE：spider在指定pipeline时需要注意顺序
    """
    def __init__(self):
        self.name = 'user-info' # 根据此选择可处理的spider
        
    def process_item(self, item, spider):
        """ 将item存储与数据库中
        """
        # 如果该pipelien不在spider的指定的pipeline中，则直接忽略
        if self.name not in getattr(spider, 'pipelines', []):
            return item
            
        # 如果已经标记了用户存在，但是不存在n_follows值
        if (item['existed'] == True) and ((not 'n_follows' in item) or (item['n_follows'] == None)):
            raise DropItem('Incomplete item: %s' % item)
        
        #import ipdb; ipdb.set_trace()
        # 检查数据库中是否有重复
        # NOTE: 该检查已经放入spider中添加request时进行检测
        #cur = spider.collection.find({'uid':item['uid']})
        #if cur.count() > 0:
        #    raise DropItem('User already in collection.')
            
        # 保存到数据库中
        # TODO: item_id = spider.collection.insert(item) # 执行该句出现错误
        item_id = spider.collection.insert(dict(item))
        
        return item
        
    def open_spider(self, spider):
        pass
        
    def close_spider(self, spider):
        pass
