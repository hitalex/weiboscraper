#coding=utf8


def beautiful_soup(html, logger=None):
    try:
        from bs4 import BeautifulSoup, FeatureNotFound
    except ImportError:
        raise DependencyNotInstalledError("BeautifulSoup4")
    
    try:
        return BeautifulSoup(html, 'lxml')
    except FeatureNotFound:
        if logger is not None:
            logger.info('lxml not installed')
        return BeautifulSoup(html)

