#coding=utf8

"""
在同一个进程开启多个相同的spider

Ref: http://stackoverflow.com/questions/22825492/how-to-stop-the-reactor-after-the-run-of-multiple-spiders-in-the-same-process-on
"""

import sys

from twisted.internet import reactor
from scrapy.crawler import Crawler
from scrapy import log, signals
from scrapy.utils.project import get_project_settings

import global_vars

class ReactorControl:

    def __init__(self):
        self.crawlers_running = 0

    def add_crawler(self):
        self.crawlers_running += 1

    def remove_crawler(self, spider, reason):
        log.msg('Spider %d closed with reason: %s.' % (spider.spider_index, reason), log.INFO)
        self.crawlers_running -= 1
        if self.crawlers_running == 0 :
            log.msg('Reactor stopped and will exit.', log.INFO)
            reactor.stop()

def setup_crawler(spider_name, index, username, passwd):
    log.msg('Starting crawler %d...' % index, log.INFO)
    crawler = Crawler(settings)
    crawler.configure()
    crawler.signals.connect(reactor_control.remove_crawler, signal=signals.spider_closed)
    spider = crawler.spiders.create(spider_name, index = index, username=username, passwd = passwd)
    crawler.crawl(spider)
    reactor_control.add_crawler()
    crawler.start()
    
    import time
    time.sleep(5)
    log.msg('Crawler %d started...' % index, log.INFO)
    
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print 'python %s <uid-list-path>' % sys.argv[1]
        sys.exit(0)
        
    uid_list_path = sys.argv[1]
    # 初始化全局变量
    global_vars.init(uid_list_path)
    
    spider_name = 'userinfo'
    
    reactor_control = ReactorControl()
    log.start(loglevel = log.DEBUG, logstdout = False)
    settings = get_project_settings()
    #crawler = Crawler(settings)
    # 从配置文件中获取微博账户信息
    weibo_accounts = settings.getlist('WEIBO_USER_ACCOUNTS')
    
    for i in range(len(weibo_accounts)):
        setup_crawler(spider_name, i, weibo_accounts[i]['username'], weibo_accounts[i]['passwd'])

    reactor.run()
