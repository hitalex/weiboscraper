#coding=utf8

"""
The parser code is borrowed from : https://github.com/chineking/cola/blob/master/contrib/weibo/parsers.py
"""

import scrapy
import pymongo

from utils import beautiful_soup
from weiboscraper.items import UserInfoItem
from weiboscraper.settings import USER_NAME, USER_PASS
from weiboscraper.utils.login import WeiboLogin

class UserInfoSpider(scrapy.Spider):
    allowed_domains = ["weibo.com"]
    start_urls = [
        "http://weibo.com/2887339314/info", # 吴军博士
    ]
    
    def __init__(self, name, **kwargs):
        self.logined = False
        super(WeiboSearchSpider, self).__init__(name, **kwargs)
        
        # 登录网站
        login = WeiboLogin(username=USER_NAME, passwd=USER_PASS)
        result = login.login()
        if result:
            self.logined = True
        else:
            print 'Logg in error'
    
    def _check_url(self, dest_url, src_url):
        # 判断参数前的url是否相同
        return dest_url.split('?')[0] == src_url.split('?')[0]
    
    def check(self, url, br):
        # 判断是否是否发生了跳转
        dest_url = br.geturl()
        if not self._check_url(dest_url, url):
            # 如果确实发生跳转，则判断是那种情况：未登录或用户不存在
            if dest_url.startswith('http://weibo.com/login.php'):
                raise WeiboLoginFailure('Weibo not login or login expired')
            if dest_url.startswith('http://weibo.com/sorry?usernotexists'):
                self.bundle.exists = False
                return False
                
            #return False
            
        return True 
        
        
    def check_page(self, response):
        url = 'http://weibo.com/'
        request = response.request.replace(url=url, method='get', callback=self.parse_item)
        return request
        
    def parse(self, response): # 默认的回调函数
        # 从用户的信息页面抽取user info
        user_info_item = UserInfoItem()
        
        # bs4解析
        soup = beautiful_soup(response)
        
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
                    user_info_item.avatar = header_soup.find('div', attrs={'class': 'pf_head_pic'})\
                                                .find('img')['src']
                    user_info_item.n_follows = int(header_soup.find('ul', attrs={'class': 'user_atten'})\
                                                    .find('strong', attrs={'node-type': 'follow'}).text)
                    user_info_item.n_fans = int(header_soup.find('ul', attrs={'class': 'user_atten'})\
                                                 .find('strong', attrs={'node-type': 'fans'}).text)
                elif domid.startswith('Pl_Core_T8CustomTriColumn__'):
                    # new style friends info
                    header_soup = beautiful_soup(data['html'])
                    tds = header_soup.find('table', attrs={'class': 'tb_counter'})\
                                                .find_all('td')
                    user_info_item.n_follows = int(tds[0].find('strong').text)
                    user_info_item.n_fans = int(tds[1].find('strong').text)
                elif domid.startswith('Pl_Official_Headerv6__'):
                    # new style avatar info
                    header_soup = beautiful_soup(data['html'])
                    user_info_item.avatar = header_soup.find('p', attrs='photo_wrap')\
                                                .find('img')['src']
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
                    user_info_item.avatar = soup.find('img')['src']
        
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
                    setattr(user_info_item, profile_map[k]['field'], v)
                
        user_info_item.work = []
        if career_div is not None:
            if not new_style:
                for div in career_div.find_all(attrs={'class': 'con'}):
                    work_info = WorkInfo()
                    ps = div.find_all('p')
                    for p in ps:
                        a = p.find('a')
                        if a is not None:
                            work_info.name = a.text
                            text = p.text
                            if '(' in text:
                                work_info.date = text.strip().split('(')[1].strip(')')
                        else:
                            text = p.text
                            if text.startswith(u'地区：'):
                                work_info.location = text.split(u'：', 1)[1]
                            elif text.startswith(u'职位：'):
                                work_info.position = text.split(u'：', 1)[1]
                            else:
                                work_info.detail = text
                    user_info_item.work.append(work_info)
            else:
                li = career_div.find('li', attrs={'class': 'li_1'})
                for span in li.find_all('span', attrs={'class': 'pt_detail'}):
                    work_info = WorkInfo()
                    
                    text = span.text
                    a = span.find('a')
                    if a is not None:
                        work_info.name = a.text
                    if '(' in text:
                        work_info.date = text.strip().split('(')[1]\
                                            .replace('\r', '')\
                                            .replace('\n', '')\
                                            .replace('\t', '')\
                                            .split(')', 1)[0]

                    for l in text.split('\r\n'):
                        l = l.strip()
                        if len(l) == 0:
                            continue
                        if l.startswith(u'地区：'):
                            work_info.location = l.split(u'：', 1)[1]
                        elif l.startswith(u'职位：'):
                            work_info.position = l.split(u'：', 1)[1]
                        else:
                            work_info.detail = text.replace('\r', '')\
                                                    .replace('\n', '')\
                                                    .replace('\t', '')\
                                                    .strip()
                    
                    user_info_item.work.append(work_info)
            
        user_info_item.edu = []
        if edu_div is not None:
            if not new_style:
                for div in edu_div.find_all(attrs={'class': 'con'}):
                    edu_info = EduInfo()
                    ps = div.find_all('p')
                    for p in ps:
                        a = p.find('a')
                        text = p.text
                        if a is not None:
                            edu_info.name = a.text
                            if '(' in text:
                                edu_info.date = text.strip().split('(')[1].strip().strip(')')
                        else:
                            edu_info.detail = text
                    user_info_item.edu.append(edu_info)
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
                    
                    edu_info = EduInfo()
                    edu_info.name = name
                    if '(' in text:
                        edu_info.date = t.strip().split('(')[1]\
                                            .replace('\r', '')\
                                            .replace('\n', '')\
                                            .replace('\t', '')\
                                            .split(')', 1)[0]
                        t = t[t.find(')')+1:]
                    text = text[end_pos:]
                    edu_info.detail = t.replace('\r', '').replace('\n', '')\
                                        .replace('\t', '').strip()
                    user_info_item.edu.append(edu_info)
                    
        user_info_item.tags = []
        if tags_div is not None:
            if not new_style:
                for div in tags_div.find_all(attrs={'class': 'con'}):
                    for a in div.find_all('a'):
                        user_info_item.tags.append(a.text)
            else:
                for a in tags_div.find('span', attrs={'class': 'pt_detail'}).find_all('a'):
                    user_info_item.tags.append(a.text.strip())
                
        
#         self.logger.debug('parse %s finish' % url)
        print user_info_item
        return user_info_item
