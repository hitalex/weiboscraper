# -*- coding: utf-8 -*-

# Scrapy settings for weiboscraper project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'weiboscraper'

SPIDER_MODULES = ['weiboscraper.spiders']
NEWSPIDER_MODULE = 'weiboscraper.spiders'

STATS_CLASS = 'weiboscraper.stats.ItemStatsCollector' # 自定义数据收集器

ITEM_PIPELINES = {
    'weiboscraper.pipelines.UserInfoPipeline': 100,
}

SPIDER_MIDDLEWARES = {
    'scrapy.contrib.spidermiddleware.referer.RefererMiddleware': True,
}

MYEXT_ENABLED = False
EXTENSIONS = {
    'weiboscraper.extensions.SpiderRequestLogging': 0,
}

# 使用自己设定的user-agent
DOWNLOADER_MIDDLEWARES = {
    'scrapy.contrib.downloadermiddleware.useragent.UserAgentMiddleware' : None,
    'weiboscraper.useragent.RotateUserAgentMiddleware' :400
}

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'weiboscraper (+http://www.yourdomain.com)'

USER_NAME = 'cola_weibo8@163.com'
USER_PASS = '31415926'

# database ralated
DB_NAME = 'kweibo'
USER_INFO_COLLECTION_NAME = 'exp_user_info'

DOWNLOAD_DELAY = 30
