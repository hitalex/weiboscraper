# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy.item import Item, Field

class WeiboscraperItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass
    
class UserInfoItem(scrapy.Item):
    # 用户信息
    # NOTE: 访问“http://weibo.com/2887339314/”会直接转到“http://weibo.com/drwujun”，也就是其个人主页
    uid = Field() # 举例：http://weibo.com/2887339314/info
    page_id = Field() # 举例：http://weibo.com/p/1035052887339314
    
    nickname = Field() # 举例：吴军博士
    username = Field() # 举例：drwujun
    
    is_verified = Field() # 是否是认证用户
    is_org = Field()    # 是否是组织
    
    avatar = Field()
    location = Field()
    sex = Field()
    birth = Field()
    blog = Field()
    site = Field()      # 个性域名
    intro = Field()     # 简介
    category = Field()  # 组织官方帐号：行业类别
    
    email = Field()
    qq = Field()
    msn = Field()
    
    n_follows = Field()
    n_fans = Field()
    
    edu = Field()
    work = Field()
    tags = Field()
    
    meta = Field()
