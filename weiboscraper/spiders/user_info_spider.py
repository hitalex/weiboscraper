#coding=utf8

"""
The parser code is borrowed from : https://github.com/chineking/cola/blob/master/contrib/weibo/parsers.py
"""
import re
import json
import time

import scrapy
import pymongo
from scrapy import Request
from scrapy import log
from scrapy.shell import inspect_response
from scrapy import signals
from scrapy.xlib.pydispatch import dispatcher

from pymongo import MongoClient

import numpy as np

from utils import beautiful_soup
from weiboscraper.items import UserInfoItem
from weiboscraper.settings import USER_NAME, USER_PASS, DB_NAME, USER_INFO_COLLECTION_NAME, WEIBO_USER_ACCOUNTS
from weiboscraper.utils.login import WeiboLogin

import global_vars # 导入全局变量

re_UserInfo = re.compile(r'^http://weibo.com/(\d+)/info')
re_UserPIDPage = re.compile(r'^http://weibo.com/p/(\d+)/')
re_UserNamePage = re.compile(r'^http://weibo.com/u/(\d+)/') # 如果用户设定了个性域名，则会跳转到个性域名
re_Site = re.compile(r'^http://weibo.com/(.*)')

re_UID = re.compile(r"CONFIG\[\'oid\'\]=\'(\d+)\'")
re_PAGEID = re.compile(r"CONFIG\[\'page_id\'\]=\'(\d+)\'")

re_UserCardAjax = re.compile(r"try\{STK\_\d+\((.*?)\)\}catch\(e\)")
re_UserCardUrl = re.compile(r"http://weibo.com/(.*?)\?")


class UserInfoSpider(scrapy.Spider):
    name = 'userinfo'
    allowed_domains = ["weibo.com"]
    
    def __init__(self, **kwargs):
        self.logined = False
        super(UserInfoSpider, self).__init__(**kwargs)
        
        self.spider_index = kwargs['index'] # the spider index
        self.username = kwargs['username']
        self.passwd = kwargs['passwd']
        # 设置登录类，对应每一个spider有一个帐号
        self.login = WeiboLogin(username = self.username, passwd = self.passwd)
        # 设置对应该spider的pipeline
        self.pipelines = ['user-info']
        
        # 数据库相关
        log.msg('Connecting the MongoDB...', log.INFO)
        self.client = MongoClient()
        self.db = self.client[DB_NAME]
        self.collection = self.db[USER_INFO_COLLECTION_NAME]
        
        log.msg('Loading uid list...')
        
        # 开始登录微博
        log.msg('Star to login account: %s' % self.username, log.INFO)
        login_url = self.login.login()
        if login_url:
            self.start_urls.append(login_url)
        else:
            print 'Log in error.'
            log.msg('Log in error. ', log.ERROR)
        
    def response_received(self):
        self.crawler.stats.inc_value('response_received')
        # 设置随机等待的时间: 假设等待时间服从Possion分布
        sec = np.random.poisson(10) # 平均值为10, 再加上scrapy的等待时间5 sec
        log.msg('Sleep for %s secs.' % sec, log.INFO)
        time.sleep(sec)
        
    def item_scraped(self):
        # 增加item统计数
        self.crawler.stats.inc_value('item_scraped')
        
    def make_request_list(self, num_request = 1):
        """ 根据当前的情况生成request的list
        """
        # 得到关于request处理的统计数据
        num_response_received= self.crawler.stats.get_value('response_received')
        num_request_issued = self.crawler.stats.get_value('request_issued')
        num_item_scraped = self.crawler.stats.get_value('item_scraped')
        num_item_response_processed = self.crawler.stats.get_value('item_response_processed')
        
        #num_request_left = num_request_issued - num_response_received # 该值可能为负值
        #log.msg('Request issued: %d, response received: %d, left: %d' % (num_request_issued, num_response_received, num_request_left), log.DEBUG)
        
        # 一个request对应一个item
        # 如果某个request不对应一个item抓取，则可以不增加 request_issued的值
        #num_request_left = num_request_issued - num_item_scraped # 该值可能为负值
        #log.msg('Request issued: %d, item scraped: %d, left: %d' % (num_request_issued, num_item_scraped, num_request_left), log.DEBUG)
        
        num_request_left = num_request_issued - num_item_response_processed
        log.msg('Request issued: %d, item response processed: %d, left: %d' % (num_request_issued, num_item_response_processed, num_request_left), log.DEBUG)
        
        log.msg('Current uidlist count: %d' % (global_vars.current_uidlist_count), log.DEBUG)
        
        request_list = []
        last_uid = ''
        if num_request_left < 5 and global_vars.current_uidlist_count < len(global_vars.UID_LIST):
            current_index = global_vars.current_uidlist_count
            while current_index < len(global_vars.UID_LIST) and len(request_list) < num_request:
                uid = global_vars.UID_LIST[current_index]
                # 检查数据库中是否已经存在该uid
                cur = self.collection.find({'uid':uid})
                if cur.count() > 0:
                    current_index += 1
                    continue
                
                #url = 'http://weibo.com/%s/info' % (uid)
                # 构造ajax url, 这是主页面的user card info
                #uid = '1642591402' # 新浪娱乐， 机构
                #uid = '3910587095' # 美少女大杂烩，未认证用户
                #uid = '1701401324' # 徐昕，认证用户
                #uid = uid_list[self.spider_index]
                url = 'http://weibo.com/aj/v6/user/newcard?ajwvr=6&id=%s&type=1&callback=STK_142251747912323' % uid
                meta = {'uid': uid, 'index': current_index}
                # 模拟header的各项参数
                if last_uid == '':
                    Referer = ''
                else:
                    Referer = 'http://weibo.com/u/5445629123/home?topnav=1&wvr=6'
                headers = {
                    'Referer': Referer,
                    'Host' : 'weibo.com',
                }
                request = Request(url=url, callback=self.parse_user_card_info, meta = meta, headers = headers)
                request_list.append(request)
                current_index += 1
                last_uid = uid
            
            global_vars.current_uidlist_count = current_index
        
        log.msg('Adding %d more requests.' % len(request_list), log.INFO)
        return request_list
        
    def parse(self, response):
        """ 处理登录url，保存cookie信息，默认的回调处理函数
        """
        #import ipdb; ipdb.set_trace()
        text = response.body
        regex = re.compile('\((.*)\)')
        data = json.loads(regex.search(text).group(1))
        userinfo = data.get('userinfo', '')
        log.msg('json data: %s' % data, level=log.INFO)
        if data['result'] == True:
            self.logined = True
            
            # 记录已经发出的request数量，每当还剩余的request数少于特定值时，则增加request
            # NOTE: request_issued不包括第一次登录时的login_url的request
            self.crawler.stats.set_value('request_issued', 0)
            # register some signals
            self.crawler.stats.set_value('response_received', 0)
            self.crawler.stats.set_value('item_scraped', 0)
            self.crawler.stats.set_value('item_response_processed', 0)

            # 记录收到的response的数量
            dispatcher.connect(self.response_received, signals.response_received)
            # 记录已经抓取的item的数量
            dispatcher.connect(self.item_scraped, signals.item_scraped)
            
            request_list = self.make_request_list(num_request = 1)
            # 将一些uid加入初始抓取的列表
            for request in request_list:
                self.crawler.stats.inc_value('request_issued')
                yield request
            
        else:
            self.log('login failed: errno=%s, reason=%s' % (data.get('errno', ''), data.get('reason', '')))
            
    def parse_user_card_info(self, response):
        """ 解析用户和机构的信息
        """
        self.crawler.stats.inc_value('item_response_processed')
        # 增加request
        request_list = self.make_request_list(5)
        for request in request_list:
            self.crawler.stats.inc_value('request_issued')
            yield request
        
        log.msg('In spider %d - Parsing response url: %s' % (self.spider_index, response.url), log.DEBUG)
            
        m = re_UserCardAjax.search(response.body)
        if m is None:
            log.msg('Error parsing ajax response: %s' % reponse.url, log.ERROR)
        else:
            json_str = m.group(1)            
            json_data = json.loads(json_str)
            uid = response.meta['uid']
            if json_data['code'] != '100000':
                log.msg('Error in response, uid: %s, msg: %s' % (uid, json_data['msg']), log.ERROR)
            else:
                html_data = json_data['data']
                user_info_item = self.parse_user_card_info_text(uid, html_data)
                log.msg('Sucess in crawling user: %s' % user_info_item['uid'])
                #print user_info_item
                yield user_info_item
        
    def parse_user_card_info_text(self, uid, html_data):
        """ 给定html body解析 user info, 用户信息包括：avatar, uid, nickname, desc, location
        NOTE: 将该解析单独作为一个函数有两个作用：1）便于单独测试；2）使得parse_user_card_info函数结构清晰
        """
        user_info_item = UserInfoItem()
        user_info_item['raw_html'] = html_data # 保存所有的原始数据
        user_info_item['uid'] = uid
        
        soup = beautiful_soup(html_data)
        
        nc_head = soup.find('div', attrs={'class':'nc_head'})
        nc_content = soup.find('div', attrs={'class':'nc_content'})
        
        pic_box = nc_head.find('div', attrs={'class':'pic_box'})
        alist = pic_box.find_all('a')
        
        url = alist[0]['href']
        m = re_UserCardUrl.search(url)
        user_info_item['username'] = m.group(1)
        if user_info_item['username'][:2] == 'u/':
            user_info_item['username'] = user_info_item['username'][2:]
            
        user_info_item['nickname'] = pic_box.a.img['title']
        user_info_item['avatar'] = pic_box.a.img['src']
        
        user_info_item['is_org'] = False
        if len(alist) > 1:
            user_info_item['is_verified'] = True
            # 判断该帐号是组织帐号还是认证用户
            if alist[1].i['class'][1] == 'icon_pf_approve_co':
                user_info_item['is_org'] = True
        else:
            user_info_item['is_verified'] = False
                            
        mask = nc_head.find('div', attrs={'class':'mask'})
        name = mask.find('div', attrs={'class':'name'})
        user_info_item['nickname'] = name.a['title']
        if name.em['title'] == u'男':
            user_info_item['sex'] = True
        else:
            user_info_item['sex'] = False
            
        intro = mask.find('div', attrs={'class':'intro W_autocut'})
        if intro.text.strip() != '':  # 可能个人简介不存在
            user_info_item['intro'] = intro.span['title']
        
        # 关注数和粉丝数
        def parse_number(text):
            # 抽取关注数和粉丝数
            num = int(re.search(r'\d+', text).group())
            if text.find(u'万') >= 0:
                num *= 10000
            return num
            
        follow_text = nc_content.find('span', attrs={'class':'c_follow W_fb'}).text.strip()
        user_info_item['n_follows'] = parse_number(follow_text)
        fans_text = nc_content.find('span', attrs={'class':'c_fans W_fb'}).text.strip()
        user_info_item['n_fans'] = parse_number(fans_text)
        weibo_text = nc_content.find('span', attrs={'class':'c_weibo W_fb'}).text.strip()
        user_info_item['n_weibo'] = parse_number(weibo_text)
        
        user_info_list = nc_content.find_all('li', attrs={'class':'info_li'})
        user_info_item['location'] = user_info_list[0].a['title']
        if len(user_info_list) >= 2:
            if user_info_list[1].text.find(u'毕业于') >= 0:
                user_info_item['edu'] = user_info_list[1].a['title']
                if len(user_info_list) >= 3:
                    user_info_item['work'] = user_info_list[2].a['title']
            else:
                user_info_item['work'] = user_info_list[1].a['title']
        
        return user_info_item

    def parse_org_info(self, response):
        """ 抽取组织主页的信息
        """
        request_list = self.make_request_list()
        for request in request_list:
            self.crawler.stats.inc_value('request_issued')
            yield request
            
        user_info_item = UserInfoItem()
        user_info_item['is_org'] = True
        user_info_item['uid'] = response.meta['uid']
        
        #import ipdb; ipdb.set_trace()
        # find user name
        # 发生了跳转，则意味着该帐号有个性域名
        m = re_UserNamePage.search(response.url)
        if m != None:
            user_info_item['username'] = user_info_item['uid']
        else:
            m = re_Site.search(response.url)
            user_info_item['username'] = m.group(1)
            
        soup = beautiful_soup(response.body)
        for script in soup.find_all('script'):
            text = script.text
            if text.startswith('FM.view'):
                text = text.strip().replace(';', '').replace('FM.view(', '')[:-1]
                data = json.loads(text)
                domid = data['domid']
                if domid.startswith('Pl_Core_T8CustomTriColumn__'):
                    info_soup = beautiful_soup(data['html'])
                    td_list = info_soup.find_all('td', attrs = {'class':'S_line1'})
                    if len(td_list) != 3:
                        log.msg('Error parsing: %s' % response.url, log.INFO)
                    else:
                        user_info_item['n_follows'] = int(td_list[0].find('strong').text.strip())
                        user_info_item['n_fans'] = int(td_list[1].find('strong').text.strip())
                        
                elif domid.startswith('Pl_Core_UserInfo__'):
                    info_soup = beautiful_soup(data['html'])
                    user_info_item['nickname'] = info_soup.find('p', attrs={'class':'info'}).find('span').text.strip()
                    ul_list = info_soup.find('ul', attrs={'class':'ul_detail'})
                    li_list = ul_list.find_all('li', attrs={'class':'item S_line2 clearfix'})
                    if len(li_list) == 0:
                        log.msg('Error parsing: %s' % response.url, log.INFO)
                    else:
                        user_info_item['category'] = li_list[0].find('span', attrs={'class':'item_text W_fl'}).text.strip()
                        if len(li_list) > 1:
                            user_info_item['intro'] = li_list[1].find('span', attrs={'class':'item_text W_fl'}).text.strip()
                    
                else:
                    pass
        
        #print user_info_item
        #import ipdb; ipdb.set_trace()
        
        yield user_info_item
        
    def parse_user_info(self, response): # 默认的回调函数
        """ 普通用户信息抓取，例如：
        """
        #import ipdb; ipdb.set_trace()
        
        # 添加接下来要处理的request
        request_list = self.make_request_list()
        for request in request_list:
            self.crawler.stats.inc_value('request_issued')
            yield request
        
        is_valid = True # 判别是否是合法的item
        log.msg('Parse url: %s' % response.url, level=log.INFO)
        #log.msg('Response body: %s' % response.body)
        
        # 如果是组织页面，那么会返回错误页面
        if response.url.find('pagenotfound') > 0:
            # 匹配源request
            #import ipdb; ipdb.set_trace()
            is_valid = False
            log.msg('Page not found: %s' % response.url, log.ERROR)
            uid = response.meta['uid']
            new_url = 'http://weibo.com/u/%s' % (uid) # 直接访问组织帐号的首页
            request = Request(url=new_url, callback=self.parse_org_info, meta={'uid':uid})
            self.crawler.stats.inc_value('request_issued')
            yield request
        
        # TODO: 判断用户是否存在， http://weibo.com/sorry?usernotexists&code=100001。
        # 不过用户确实是存在的
        # TODO: 判断被封：http://weibo.com/sorry?userblock&is_viewer&code=20003
        # http://sass.weibo.com/accessdeny?uid=5445629123&ip=2682434316&location=1&callbackurl=http%3A%2F%2Fweibo.com%2Fu%2F2029154257
        
        # 从用户的信息页面抽取user info
        user_info_item = UserInfoItem()
        user_info_item['is_org'] = False
        
        # 从原始返回的页面中抽取uid和page_id
        m = re_UID.search(response.body)
        if m != None:
            user_info_item['uid'] = m.group(1)
        else:
            log.msg('Error parsing uid: %s' % response.url, log.ERROR)
            
        # 抽取page_id
        m = re_PAGEID.search(response.body)
        if m != None:
            user_info_item['page_id'] = m.group(1)
        else:
            log.msg('Error parsing page id: %s' % response.url, log.ERROR)
        
        # bs4解析
        soup = beautiful_soup(response.body)
        
        new_style = False
        profile_div = None
        career_div = None
        edu_div = None
        tags_div = None
        for script in soup.find_all('script'):
            text = script.text
            if text.startswith('FM.view'):
                text = text.strip().replace(';', '').replace('FM.view(', '')[:-1]
                data = json.loads(text)
                domid = data['domid']
                if domid.startswith('Pl_Official_LeftInfo__'):
                    info_soup = beautiful_soup(data['html'])
                    info_div = info_soup.find('div', attrs={'class': 'profile_pinfo'})
                    for block_div in info_div.find_all('div', attrs={'class': 'infoblock'}):
                        block_title = block_div.find('form').text.strip()
                        if block_title == u'基本信息':
                            profile_div = block_div
                        elif block_title == u'工作信息':
                            career_div = block_div
                        elif block_title == u'教育信息':
                            edu_div = block_div
                        elif block_title == u'标签信息':
                            tags_div = block_div
                elif domid.startswith('Pl_Official_PersonalInfo__'):
                    new_style = True
                    info_soup = beautiful_soup(data['html'])
                    for block_div in info_soup.find_all('div', attrs={'class': 'WB_cardwrap'}):
                        block_title = block_div.find('h4', attrs={'class': 'obj_name'}).text.strip()
                        inner_div = block_div.find('div', attrs={'class': 'WB_innerwrap'})
                        if block_title == u'基本信息':
                            profile_div = inner_div
                        elif block_title == u'工作信息':
                            career_div = inner_div
                        elif block_title == u'教育信息':
                            edu_div = inner_div
                        elif block_title == u'标签信息':
                            tags_div = inner_div
                elif domid == 'Pl_Official_Header__1':
                    header_soup = beautiful_soup(data['html'])
                    user_info_item['avatar'] = header_soup.find('div', attrs={'class': 'pf_head_pic'})\
                                                .find('img')['src']
                    user_info_item['n_follows'] = int(header_soup.find('ul', attrs={'class': 'user_atten'})\
                                                    .find('strong', attrs={'node-type': 'follow'}).text)
                    user_info_item['n_fans'] = int(header_soup.find('ul', attrs={'class': 'user_atten'})\
                                                 .find('strong', attrs={'node-type': 'fans'}).text)
                elif domid.startswith('Pl_Core_T8CustomTriColumn__'):
                    # new style friends info
                    header_soup = beautiful_soup(data['html'])
                    tds = header_soup.find('table', attrs={'class': 'tb_counter'})\
                                                .find_all('td')
                    user_info_item['n_follows'] = int(tds[0].find('strong').text)
                    user_info_item['n_fans'] = int(tds[1].find('strong').text)
                elif domid.startswith('Pl_Official_Headerv6__'):
                    # new style avatar info
                    header_soup = beautiful_soup(data['html'])
                    user_info_item['avatar'] = header_soup.find('p', attrs='photo_wrap')\
                                                .find('img')['src']
                    
                    #import ipdb; ipdb.set_trace()
                    # 判别该用户是否是认真用户
                    photo_div = header_soup.find_all('div', attrs={'class':'pf_photo', 'node-type':'photo'})
                    if len(photo_div) > 0:
                        result = photo_div[0].find_all('a', attrs={'href':'http://verified.weibo.com/verify'})
                        if len(result) > 0:
                            user_info_item['is_verified'] = True
                        else:
                            user_info_item['is_verified'] = False
                    else:
                        log.msg('Can not find photo div: %s' % response.url, log.ERROR)
                    
            elif 'STK' in text:
                text = text.replace('STK && STK.pageletM && STK.pageletM.view(', '')[:-1]
                data = json.loads(text)
                pid = data['pid']
                if pid == 'pl_profile_infoBase':
                    profile_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_infoCareer':
                    career_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_infoEdu':
                    edu_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_infoTag':
                    tags_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_photo':
                    soup = beautiful_soup(data['html'])
                    user_info_item['avatar'] = soup.find('img')['src']
        
        profile_map = {
            u'昵称': {'field': 'nickname'},
            u'所在地': {'field': 'location'},
            u'性别': {'field': 'sex', 
                    'func': lambda s: True if s == u'男' else False},
            u'生日': {'field': 'birth'},
            u'博客': {'field': 'blog'},
            u'个性域名': {'field': 'site'},
            u'简介': {'field': 'intro'},
            u'邮箱': {'field': 'email'},
            u'QQ': {'field': 'qq'},
            u'MSN': {'field': 'msn'}
        }
        if profile_div is not None:
            if not new_style:
                divs = profile_div.find_all(attrs={'class': 'pf_item'})
            else:
                divs = profile_div.find_all('li', attrs={'class': 'li_1'})
            for div in divs:
                if not new_style:
                    k = div.find(attrs={'class': 'label'}).text.strip()
                    v = div.find(attrs={'class': 'con'}).text.strip()
                else:
                    k = div.find('span', attrs={'class': 'pt_title'}).text.strip().strip(u'：')
                    d = div.find('span', attrs={'class': 'pt_detail'})
                    if d:
                        v = d.text.strip()
                    else:
                        v = div.find('a').text.strip()
                if k in profile_map:
                    if k == u'个性域名' and '|' in v:
                        v = v.split('|')[1].strip()
                    func = (lambda s: s) \
                            if 'func' not in profile_map[k] \
                            else profile_map[k]['func']
                    v = func(v)
                    user_info_item[profile_map[k]['field']] = v
                    #setattr(user_info_item, profile_map[k]['field'], v)
                
        user_info_item['work'] = []
        if career_div is not None:
            if not new_style:
                for div in career_div.find_all(attrs={'class': 'con'}):
                    work_info = dict()
                    ps = div.find_all('p')
                    for p in ps:
                        a = p.find('a')
                        if a is not None:
                            work_info['name'] = a.text
                            text = p.text
                            if '(' in text:
                                work_info['date'] = text.strip().split('(')[1].strip(')')
                        else:
                            text = p.text
                            if text.startswith(u'地区：'):
                                work_info['location'] = text.split(u'：', 1)[1]
                            elif text.startswith(u'职位：'):
                                work_info['position'] = text.split(u'：', 1)[1]
                            else:
                                work_info['detail'] = text
                    user_info_item['work'].append(work_info)
            else:
                li = career_div.find('li', attrs={'class': 'li_1'})
                for span in li.find_all('span', attrs={'class': 'pt_detail'}):
                    work_info = dict()
                    
                    text = span.text
                    a = span.find('a')
                    if a is not None:
                        work_info['name'] = a.text
                    if '(' in text:
                        work_info['date'] = text.strip().split('(')[1]\
                                            .replace('\r', '')\
                                            .replace('\n', '')\
                                            .replace('\t', '')\
                                            .split(')', 1)[0]

                    for l in text.split('\r\n'):
                        l = l.strip()
                        if len(l) == 0:
                            continue
                        if l.startswith(u'地区：'):
                            work_info['location'] = l.split(u'：', 1)[1]
                        elif l.startswith(u'职位：'):
                            work_info['position'] = l.split(u'：', 1)[1]
                        else:
                            work_info['detail'] = text.replace('\r', '')\
                                                    .replace('\n', '')\
                                                    .replace('\t', '')\
                                                    .strip()
                    
                    user_info_item['work'].append(work_info)
            
        user_info_item['edu'] = []
        if edu_div is not None:
            if not new_style:
                for div in edu_div.find_all(attrs={'class': 'con'}):
                    edu_info = dict()
                    ps = div.find_all('p')
                    for p in ps:
                        a = p.find('a')
                        text = p.text
                        if a is not None:
                            edu_info['name'] = a.text
                            if '(' in text:
                                edu_info['date'] = text.strip().split('(')[1].strip().strip(')')
                        else:
                            edu_info['detail'] = text
                            
                    user_info_item['edu'].append(edu_info)
            else:
                span = edu_div.find('li', attrs={'class': 'li_1'})\
                                .find('span', attrs={'class': 'pt_detail'})
                text = span.text
                names = []
                for a in span.find_all('a'):
                    names.append(a.text)
                
                for idx, name in enumerate(names):
                    start_pos = text.find(name) + len(name)
                    if idx < len(names) - 1:
                        end_pos = text.find(names[idx+1], start_pos)
                    else:
                        end_pos = len(text)
                    t = text[start_pos: end_pos]
                    
                    edu_info = dict()
                    edu_info['name'] = name
                    if '(' in text:
                        edu_info['date'] = t.strip().split('(')[1]\
                                            .replace('\r', '')\
                                            .replace('\n', '')\
                                            .replace('\t', '')\
                                            .split(')', 1)[0]
                        t = t[t.find(')')+1:]
                    text = text[end_pos:]
                    edu_info['detail'] = t.replace('\r', '').replace('\n', '')\
                                        .replace('\t', '').strip()
                    user_info_item['edu'].append(edu_info)
                    
        user_info_item['tags'] = []
        if tags_div is not None:
            if not new_style:
                for div in tags_div.find_all(attrs={'class': 'con'}):
                    for a in div.find_all('a'):
                        user_info_item['tags'].append(a.text)
            else:
                for a in tags_div.find('span', attrs={'class': 'pt_detail'}).find_all('a'):
                    user_info_item['tags'].append(a.text.strip())
                
        # 如果打算将item包含进去，则is_valid则为True
        log.msg('parse %s finish' % response.url, log.INFO)
        
        # 检查spider是否已经被封
        if not user_info_item['n_follows']:
            log.msg('The spider may have been banned.', log.ERROR)
        else:
            if is_valid:
                #print user_info_item
                yield user_info_item
            

if __name__ == '__main__':
    spider = UserInfoSpider()
