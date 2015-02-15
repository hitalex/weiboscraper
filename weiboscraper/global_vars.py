#coding=utf8

"""
包含一些全局变量
"""

from spiders.utils import load_uid_list
from scrapy import log

from pymongo import MongoClient

def init(uid_list_path):
    global current_uidlist_count, UID_LIST, CURRENT_ALL_USER_SET
    #UID_LIST = load_uid_list('/home/kqc/github/weiboscraper/weiboscraper/data/user-list-sample-1000.txt')
    UID_LIST = load_uid_list(uid_list_path)
    current_uidlist_count = 0
    
    # 导入所有当前已经在数据库中的uid的集合
    # 避免重复查询数据库
    print 'Loading all users from db.'
    client = MongoClient()
    db = client['kweibo']
    collection = db['exp_user_info']
    
    CURRENT_ALL_USER_SET = set()
    for user in collection.find():
        CURRENT_ALL_USER_SET.add(user['uid'])
        
    print 'Loading %d users in total.' % len(CURRENT_ALL_USER_SET)
