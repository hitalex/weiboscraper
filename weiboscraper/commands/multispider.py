#coding=utf8

"""
开启多个spider

Ref: http://blog.csdn.net/iefreer/article/details/20677943
"""

from scrapy.command import ScrapyCommand
from scrapy.utils.project import get_project_settings
from scrapy.crawler import Crawler

class Command(ScrapyCommand):

    requires_project = True

    def syntax(self):
        return '[options]'

    def short_desc(self):
        return 'Runs multi-spiders'

    def run(self, args, opts):
        settings = get_project_settings()
        spider_name = 'userinfo'
        num_crawler_instance = len(settings.getlist('WEIBO_USER_ACCOUNT'))
        for i in range(num_crawler_instance):
            crawler = Crawler(settings)
            crawler.configure()
            spider = crawler.spiders.create(spider_name)
            crawler.crawl(spider)
            crawler.start()

        self.crawler.start()