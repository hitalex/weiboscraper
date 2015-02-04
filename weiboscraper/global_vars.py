#coding=utf8

"""
包含一些全局变量
"""

from spiders.utils import load_uid_list

def init(uid_list_path):
    global current_uidlist_count, UID_LIST
    #UID_LIST = load_uid_list('/home/kqc/github/weiboscraper/weiboscraper/data/user-list-sample-1000.txt')
    UID_LIST = load_uid_list(uid_list_path)
    current_uidlist_count = 0
