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
import logging
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
    def _element_to_html(element: requests_html.Element) -> str:
        return element.pq.outer_html()

    if isinstance(elements, requests_html.Element):
        return _element_to_html(elements)
    else:
        return ''.join([_element_to_html(element) for element in elements])


def guess_mime_type(url: str) -> str:
    mime_type = epub.guess_type(url)[0]
    return '' if mime_type is None else mime_type


class Generator:
    def __init__(self):
        self.site_url = 'https://zh.gluon.ai/'
        self.session = HTMLSession()

    def __del__(self):
        self.session.close()

    def generate(self):
        self.book = epub.EpubBook()
        self.book.spine = []
        self.download_page()

        logger.info('add local resources')
        rc_root_path = os.path.join(os.path.dirname(__file__), '..')
        for dir_path, _dir_names, file_names in os.walk(
                os.path.join(rc_root_path, 'cdnjs.cloudflare.com')):
            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)
                with open(file_path, 'rb') as item_file:
                    item_content = item_file.read()
                    item_path = os.path.relpath(file_path, rc_root_path)
                    if os.path.sep != '/':
                        item_path = item_path.replace(os.path.sep, '/')
                    self.book.add_item(
                        epub.EpubItem(
                            file_name=item_path,
                            media_type=guess_mime_type(file_name),
                            content=item_content))

        epub.write_epub('gluon_tutorials_zh.epub', self.book)

    def download_page(self, page_path='index.html'):
        logger.info('download ' + self.site_url + page_path)
        response = self.session.get(self.site_url + page_path)
        html = response.html

        css_list = html.find('link[type="text/css"]')
        css_list = list(
            filter(
                lambda css: '_static/css/theme.css' not in css.attrs['href'],
                css_list))
        head_script_list = html.find('head script')
        main_document_div = html.find('div[role="main"]', first=True)
        img_list = main_document_div.find('img')
        body_script_list = html.find('body script')
        body_script_list = list(
            filter(filter_useless_scripts, body_script_list))

        self.download_resource(css_list, 'href', 'text/css', page_path)
        self.download_resource(head_script_list, 'src',
                               'application/javascript', page_path)
        self.download_resource(body_script_list, 'src',
                               'application/javascript', page_path)
        self.download_resource(img_list, 'src', '', page_path)

        epub_item = epub.EpubItem(
            file_name=page_path,
            media_type='text/html',
            content=
            '<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" epub:prefix="z3998: http://www.daisy.org/z3998/2012/vocab/structure/#" class="no-js" lang="zh-CN" xml:lang="zh-CN"><head>'
            + elements_to_html(css_list) + elements_to_html(head_script_list) +
            '</head><body>' + elements_to_html(main_document_div) +
            elements_to_html(body_script_list) + '</body></html>')
        self.book.add_item(epub_item)
        self.book.spine.append(epub_item)

        if page_path == 'index.html':
            book_title = html.find('h1', first=True).text.strip('¶')
            self.book.set_title(book_title)
            self.book.set_language('cn')
            self.create_toc(
                main_document_div.find(
                    'div.toctree-wrapper,.compound', first=True), page_path,
                book_title)

    def create_toc(self, toc_div: requests_html.Element, index_page_path: str,
                   book_title: str):
        book_toc = [epub.Link(index_page_path, book_title, index_page_path)]
        child_page_path_list = []
        for l1_li in toc_div.find('li.toctree-l1'):
            l1_link = l1_li.find('li.toctree-l1 > a', first=True)
            l1_link_href = l1_link.attrs['href']
            l1_toc = [epub.Section(l1_link.text)]
            child_page_path_list.append(l1_link_href)

            l2_toc = [epub.Link(l1_link_href, l1_link.text, l1_link_href)]
            for l2_link in l1_li.find('li.toctree-l2 > a'):
                l2_link_href = l2_link.attrs['href']
                l2_toc.append(
                    epub.Link(l2_link_href, l2_link.text, l2_link_href))
                child_page_path_list.append(l2_link_href)

            l1_toc.append(l2_toc)
            book_toc.append(l1_toc)

        for child_page_path in child_page_path_list:
            self.download_page(child_page_path)

        self.book.toc = book_toc
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

    def download_resource(self,
                          element_list: List[requests_html.Element],
                          element_path_attr: str,
                          media_type='',
                          page_path='index.html'):
        try:
            base_href = page_path[:page_path.rindex('/') + 1]
            http_rc_path_prefix = len(base_href[:-1].split('/')) * '../'
        except ValueError:
            base_href = ''
            http_rc_path_prefix = ''

        for element in element_list:
            if element_path_attr not in element.attrs:
                continue
            element_path: str = element.attrs[element_path_attr]

            if element_path.startswith('http://') or element_path.startswith(
                    'https://'):
                rc_url = element_path
                element_path = element_path[element_path.index('://') + 3:]
                element.pq.attr(element_path_attr,
                                http_rc_path_prefix + element_path)
                try:
                    rc_path = element_path[:element_path.index('?')]
                except ValueError:
                    rc_path = element_path
            else:
                rc_path = evaluate_path(base_href + element_path)
                rc_url = self.site_url + rc_path

            if self.book.get_item_with_href(rc_path) is not None:
                continue
            if rc_path.startswith('cdnjs.cloudflare.com/'):
                continue
            logger.info('download ' + rc_url)
            rc_content = self.session.get(rc_url).content

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
                    rc_media_type = guess_mime_type(rc_path)
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
