#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2018 Xianguang Zhou <xianguang.zhou@outlook.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from typing import List
import os
import sys
import asyncio
import logging
import pyppeteer
import requests_html
from requests_html import HTMLSession
from ebooklib import epub

__author__ = 'Xianguang Zhou <xianguang.zhou@outlook.com>'
__copyright__ = 'Copyright (C) 2018 Xianguang Zhou <xianguang.zhou@outlook.com>'
__license__ = 'AGPL-3.0'

logger = logging.getLogger('EpubGen')
logger.setLevel(logging.INFO)
logger_console_handler = logging.StreamHandler(sys.stdout)
logger_console_handler.formatter = logging.Formatter(
    '%(levelname)s: %(message)s')
logger.addHandler(logger_console_handler)


def evaluate_path(path: str) -> str:
    name_list = path.split('/')
    name_list_index = 1
    while name_list_index < len(name_list):
        if name_list[name_list_index] == '..':
            name_list_index -= 1
            del name_list[name_list_index]
            del name_list[name_list_index]
        else:
            name_list_index += 1
    return '/'.join(name_list)


def filter_useless_scripts(script_element: requests_html.Element) -> bool:
    attrs = script_element.attrs
    if 'src' in attrs:
        src: str = attrs['src']
        if 'baidu_tongji' in src:
            return False
        elif 'google_analytics' in src:
            return False
        else:
            return True
    else:
        if 'SphinxRtdTheme.Navigation' in script_element.text:
            return False
        else:
            return True


def elements_to_html(elements) -> str:
    if type(elements) == list:
        return ''.join([element.html for element in elements])
    else:
        return elements.html


class Generator:
    def __init__(self):
        self.site_url = 'https://zh.gluon.ai/'
        self.event_loop = asyncio.get_event_loop()
        self.book = epub.EpubBook()
        self.session = HTMLSession()
        self.browser = self.event_loop.run_until_complete(pyppeteer.launch(
            executablePath='/usr/bin/google-chrome-stable',
            headless=True,
            args=[
                '--no-sandbox', '--disk-cache-dir=/dev/shm/' +
                os.environ['USER'] + '/chrome/cache',
                '--disk-cache-size=367001600'
            ]))

    def __del__(self):
        self.event_loop.run_until_complete(self.browser.close())
        self.session.close()
        self.event_loop.close()

    def generate(self):
        self.download_page()
        # epub.write_epub('gluon_tutorials_zh.epub', self.book)

    def download_page(self, page_path='index.html'):
        logger.info('download ' + self.site_url + page_path)
        response = self.session.get(self.site_url + page_path)
        html = response.html

        meta_list = html.find('meta')
        css_list = html.find('link[type="text/css"]')
        head_script_list = html.find('head > script')
        main_document_div = html.find('div[role="main"]', first=True)
        img_list = main_document_div.find('img')
        body_script_list = html.find('body > script')
        body_script_list = list(
            filter(filter_useless_scripts, body_script_list))

        self.download_resource(css_list, 'href', 'text/css', page_path)
        self.download_resource(head_script_list, 'src',
                               'application/javascript', page_path)
        self.download_resource(body_script_list, 'src',
                               'application/javascript', page_path)
        self.download_resource(img_list, 'src', '', page_path)

        # if page_path == '':
        #     self.book.set_cover(
        #         'index.html',
        #         '<!DOCTYPE html><html class="no-js" lang="zh-CN"><head>' +
        #         elements_to_html(meta_list) + elements_to_html(css_list) +
        #         elements_to_html(head_script_list) + '</head><body>' +
        #         elements_to_html(main_document_div) +
        #         elements_to_html(body_script_list) + '</body></html>')

    def download_resource(self,
                          element_list: List[requests_html.Element],
                          element_path_attr: str,
                          media_type='',
                          page_path=''):
        try:
            base_href = page_path[:page_path.rindex('/') + 1]
        except ValueError:
            base_href = ''

        for element in element_list:
            if element_path_attr not in element.attrs:
                continue
            element_path: str = element.attrs[element_path_attr]

            if element_path.startswith('http://') or element_path.startswith(
                    'https://'):
                rc_path = element_path[element_path.index('://') + 3:]
                rc_url = element_path
                element.attrs[element_path_attr] = rc_path
            else:
                rc_path = evaluate_path(base_href + element_path)
                rc_url = self.site_url + rc_path

            if self.book.get_item_with_href(rc_path) is not None:
                continue
            logger.info('download ' + rc_url)
            if rc_url.startswith('https://cdnjs.cloudflare.com/'):
                async def _download_cdn(rc_url:str):
                    # self.session.get('').html.render()
                    browser_page = await self.browser.newPage()
                    await browser_page.goto(rc_url)
                    rc_content = browser_page.content.encode('utf-8')
                    await browser_page.close()
                    return rc_content
                rc_content = self.event_loop.run_until_complete(_download_cdn(rc_url))
            else:
                rc_content = self.session.get(rc_url).content

                # headers={
                #     'Accept': '*/*',
                #     'Accept-Encoding': 'gzip, deflate, br',
                #     'Accept-Language': 'zh,zh-CN;q=0.8,en-US;q=0.5,en;q=0.3',
                #     'Connection': 'keep-alive',
                #     'DNT': '1',
                #     'Referer': 'https://zh.gluon.ai/',
                #     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:56.0) Gecko/20100101 Firefox/56.0',
                # },
                # stream=True

            if media_type == '':
                if rc_path.endswith('.png'):
                    rc_media_type = 'image/png'
                elif rc_path.endswith('.jpg') or rc_path.endswith('.jpeg'):
                    rc_media_type = 'image/jpeg'
                elif rc_path.endswith('.css'):
                    rc_media_type = 'text/css'
                elif rc_path.endswith(
                        '.js') or element.element.tag == 'script':
                    rc_media_type = 'application/javascript'
                else:
                    rc_media_type = ''
            else:
                rc_media_type = media_type
            self.book.add_item(
                epub.EpubItem(
                    file_name=rc_path,
                    media_type=rc_media_type,
                    content=rc_content))


def main():
    Generator().generate()


if __name__ == '__main__':
    main()
