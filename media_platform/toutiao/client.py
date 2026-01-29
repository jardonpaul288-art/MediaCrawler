# -*- coding: utf-8 -*-
"""
今日头条API客户端 - 使用网络请求拦截获取API数据
参考小红书的实现方式
"""
import asyncio
import re
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote, urlencode

import httpx
from playwright.async_api import BrowserContext, Page, Route, Request
from tenacity import retry, stop_after_attempt, wait_fixed

from base.base_crawler import AbstractApiClient
from tools import utils


class ToutiaoClient(AbstractApiClient):
    """今日头条API客户端 - 使用网络请求拦截"""
    
    def __init__(
        self,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
        proxy: Optional[str] = None,
        timeout: int = 30,
    ):
        self.headers = headers
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict
        self.proxy = proxy
        self.timeout = timeout
        self._host = "https://so.toutiao.com"
        self._index = "https://www.toutiao.com"
        
        # 存储拦截到的API数据
        self._intercepted_data: List[Dict] = []
        # 已处理的URL去重
        self._processed_urls: Set[str] = set()
    
    async def request(self, method: str, url: str, **kwargs) -> Any:
        """发送HTTP请求"""
        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=self.timeout,
                **kwargs
            )
            return response
    
    async def update_cookies(self, browser_context: BrowserContext):
        """更新cookies"""
        cookie_str, cookie_dict = utils.convert_cookies(
            await browser_context.cookies(urls=[self._index, self._host])
        )
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict
    
    async def pong(self) -> bool:
        """检查状态 - 今日头条搜索不需要登录"""
        utils.logger.info("[ToutiaoClient.pong] 今日头条搜索不需要登录，直接使用")
        return True
    
    async def _handle_response(self, response):
        """处理拦截到的响应"""
        try:
            url = response.url
            # 跳过明显不是数据的资源
            skip_patterns = ['.js', '.css', '.png', '.jpg', '.gif', '.woff', '.ico', 'monitor', 'log', 'beacon']
            if any(pattern in url.lower() for pattern in skip_patterns):
                return
            
            # 拦截所有可能包含搜索结果的响应
            # 今日头条的数据可能在多个端点返回
            data_patterns = ['api', 'search', 'feed', 'data', 'result', 'list', 'article', 'content']
            
            if any(pattern in url.lower() for pattern in data_patterns):
                try:
                    # 检查响应类型
                    content_type = response.headers.get('content-type', '')
                    if 'json' in content_type or 'javascript' in content_type:
                        body = await response.body()
                        text = body.decode('utf-8')
                        
                        # 尝试解析JSON（可能是JSONP格式）
                        if text.startswith('(') or text.startswith('callback'):
                            # JSONP格式，提取JSON部分
                            match = re.search(r'\{.*\}', text, re.DOTALL)
                            if match:
                                text = match.group()
                        
                        if text.startswith('{') or text.startswith('['):
                            data = json.loads(text)
                            # 检查数据中是否包含文章相关字段
                            if self._looks_like_search_data(data):
                                utils.logger.info(f"[ToutiaoClient] 拦截到搜索结果API: {url[:80]}...")
                                self._intercepted_data.append({
                                    'url': url,
                                    'data': data
                                })
                except Exception as e:
                    pass
        except Exception as e:
            pass
    
    def _looks_like_search_data(self, data: Dict) -> bool:
        """检查数据是否像搜索结果"""
        if not isinstance(data, dict):
            return False
        
        # 检查是否包含文章相关的字段
        article_fields = ['title', 'article_url', 'abstract', 'source', 'media_name']
        
        def check_item(item):
            if isinstance(item, dict):
                return any(field in item for field in article_fields)
            return False
        
        # 检查 data.data
        if isinstance(data.get('data'), list):
            return any(check_item(item) for item in data['data'][:3])
        elif isinstance(data.get('data'), dict):
            inner = data['data']
            if isinstance(inner.get('data'), list):
                return any(check_item(item) for item in inner['data'][:3])
            if isinstance(inner.get('result'), list):
                return any(check_item(item) for item in inner['result'][:3])
        
        # 检查 data.result
        if isinstance(data.get('result'), list):
            return any(check_item(item) for item in data['result'][:3])
        
        return False

    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def search_posts(self, keyword: str, page: int = 1, count: int = 20) -> List[Dict]:
        """
        搜索帖子
        
        Args:
            keyword: 搜索关键词
            page: 页码（从1开始）
            count: 每页返回数量
            
        Returns:
            搜索结果列表
        """
        utils.logger.info(f"[ToutiaoClient.search_posts] 搜索关键词: {keyword}, 第 {page} 页")
        
        # 清空之前拦截的数据
        self._intercepted_data = []
        
        # 构建搜索URL（添加时间筛选：一个月内）
        encoded_keyword = quote(keyword)
        search_url = (
            f"{self._host}/search?dvpf=pc&source=input&keyword={encoded_keyword}"
            f"&pd=synthesis&filter_vendor=all&index_resource=all&filter_period=month"
        )
        
        try:
            # 注册响应拦截器
            self.playwright_page.on("response", self._handle_response)
            
            # 第一页：导航到搜索页面
            if page == 1:
                await self.playwright_page.goto(search_url)
                await asyncio.sleep(3)
            else:
                # 非第一页：滚动加载更多
                for _ in range(3):  # 每次滚动3次加载更多
                    await self.playwright_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.5)
            
            # 等待页面加载
            await asyncio.sleep(2)
            
            # 优先从拦截的API数据中解析
            if self._intercepted_data:
                results = self._parse_intercepted_data()
                if results:
                    utils.logger.info(f"[ToutiaoClient.search_posts] 从API拦截获取到 {len(results)} 条结果")
                    # 去重
                    unique_results = self._deduplicate_results(results)
                    return unique_results[:count]
            
            # 回退到DOM解析
            results = await self._extract_dom_results_improved()
            # 去重
            unique_results = self._deduplicate_results(results)
            utils.logger.info(f"[ToutiaoClient.search_posts] DOM解析获取到 {len(unique_results)} 条唯一结果")
            return unique_results[:count]
            
        except Exception as e:
            utils.logger.error(f"[ToutiaoClient.search_posts] 搜索失败: {e}")
            raise
        finally:
            # 移除响应拦截器
            try:
                self.playwright_page.remove_listener("response", self._handle_response)
            except:
                pass
    
    def _parse_intercepted_data(self) -> List[Dict]:
        """解析拦截到的API数据"""
        results = []
        
        for item in self._intercepted_data:
            try:
                data = item.get('data', {})
                
                # 尝试不同的数据路径
                items_list = None
                
                # 路径1: data.data
                if isinstance(data.get('data'), list):
                    items_list = data['data']
                # 路径2: data.data.data
                elif isinstance(data.get('data'), dict) and isinstance(data['data'].get('data'), list):
                    items_list = data['data']['data']
                # 路径3: data.result
                elif isinstance(data.get('result'), list):
                    items_list = data['result']
                
                if items_list:
                    # 打印第一条数据的所有字段，用于调试
                    if items_list and len(items_list) > 0:
                        first_item = items_list[0]
                        if isinstance(first_item, dict):
                            utils.logger.info(f"[ToutiaoClient] API返回的字段: {list(first_item.keys())}")
                            # 打印所有可能的时间相关字段
                            time_fields = ['publish_time', 'datetime', 'create_time', 'behot_time', 
                                          'display_time', 'time', 'date', 'created_at', 'publish_time_str']
                            for tf in time_fields:
                                if tf in first_item:
                                    utils.logger.info(f"[ToutiaoClient] 时间字段 {tf} = {first_item[tf]}")
                    
                    for article in items_list:
                        if not isinstance(article, dict):
                            continue
                        
                        title = article.get('title', '')
                        if not title:
                            continue
                        
                        # 获取发布时间（尝试多个可能的字段名）
                        publish_time = 0
                        
                        # 1. 直接的时间戳字段
                        for time_field in ['publish_time', 'behot_time', 'create_time', 'display_time']:
                            if article.get(time_field):
                                ts = article[time_field]
                                # 判断是10位还是13位时间戳
                                if isinstance(ts, (int, float)):
                                    if ts > 1e12:  # 13位
                                        publish_time = int(ts)
                                    else:  # 10位
                                        publish_time = int(ts) * 1000
                                    break
                        
                        # 2. 字符串日期字段
                        if not publish_time:
                            for date_field in ['datetime', 'publish_time_str', 'date', 'time']:
                                if article.get(date_field):
                                    publish_time = self._parse_date_time(str(article[date_field]))
                                    if publish_time:
                                        break
                        
                        result = {
                            'title': self._clean_html(title),
                            'content': self._clean_html(article.get('abstract', article.get('content', ''))),
                            'source': article.get('source', article.get('media_name', '')),
                            'time': article.get('datetime', article.get('publish_time_str', '')),
                            'publish_time': publish_time,
                            'url': article.get('article_url', article.get('display_url', article.get('url', ''))),
                            'user_id': str(article.get('user_id', article.get('media_id', article.get('source_id', '')))),
                        }
                        results.append(result)
                        
            except Exception as e:
                utils.logger.debug(f"[ToutiaoClient._parse_intercepted_data] 解析失败: {e}")
        
        return results
    
    def _clean_html(self, text: str) -> str:
        """清除HTML标签"""
        if not text:
            return ""
        # 移除HTML标签
        clean = re.sub(r'<[^>]+>', '', text)
        # 移除多余空格
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """去重结果"""
        unique_results = []
        seen_titles = set()
        seen_urls = set()
        
        for result in results:
            title = result.get('title', '')
            url = result.get('url', '')
            
            # 跳过重复
            if title in seen_titles or (url and url in seen_urls):
                continue
            
            # 跳过之前已处理的URL
            if url and url in self._processed_urls:
                continue
            
            seen_titles.add(title)
            if url:
                seen_urls.add(url)
                self._processed_urls.add(url)
            
            unique_results.append(result)
        
        return unique_results
    
    async def _extract_dom_results_improved(self) -> List[Dict]:
        """从页面DOM提取搜索结果（改进版）"""
        results = []
        
        try:
            # 使用更精确的选择器 - 只选择搜索结果项
            # 根据用户提供的HTML结构，每个结果在 .result-content 中
            items = await self.playwright_page.query_selector_all('.result-content')
            
            if not items or len(items) == 0:
                # 尝试备选选择器
                items = await self.playwright_page.query_selector_all('[class*="cs-view-block"]:has(a[target="_blank"])')
            
            utils.logger.info(f"[ToutiaoClient._extract_dom_results_improved] 找到 {len(items)} 个结果项")
            
            for item in items:
                try:
                    result = await self._parse_dom_item_improved(item)
                    if result and result.get('title'):
                        results.append(result)
                except Exception as e:
                    continue
                        
        except Exception as e:
            utils.logger.error(f"[ToutiaoClient._extract_dom_results_improved] 提取失败: {e}")
        
        return results
    
    async def _parse_dom_item_improved(self, item) -> Dict:
        """解析单个DOM元素（改进版）"""
        result = {
            'title': '',
            'content': '',
            'source': '',
            'time': '',
            'publish_time': 0,
            'url': '',
            'user_id': ''
        }
        
        try:
            # 获取整个元素的文本用于调试
            full_text = await item.inner_text()
            
            # 1. 提取标题和链接 - 使用最精确的选择器
            title_el = await item.query_selector('a.text-ellipsis.text-underline-hover[target="_blank"]')
            if not title_el:
                title_el = await item.query_selector('a[target="_blank"]:first-of-type')
            
            if title_el:
                result['title'] = (await title_el.inner_text()).strip()
                result['url'] = await title_el.get_attribute('href') or ''
            
            # 2. 提取时间 - 查找日期格式文本
            date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', full_text)
            if date_match:
                result['time'] = date_match.group(1)
                result['publish_time'] = self._parse_date_time(date_match.group(1))
            
            # 3. 提取来源 - 通常在时间前面
            if result['time'] and '·' in full_text:
                # 格式: "来源 · 时间"
                parts = full_text.split(result['time'])[0] if result['time'] in full_text else ''
                if '·' in parts:
                    source = parts.split('·')[-1].strip()
                    result['source'] = source
            
            # 4. 提取内容摘要
            # 内容通常是较长的文本段落
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]
            for line in lines:
                if len(line) > 30 and line != result['title'] and result['time'] not in line:
                    result['content'] = line[:200]
                    break
            
        except Exception as e:
            utils.logger.debug(f"[ToutiaoClient._parse_dom_item_improved] 解析失败: {e}")
        
        return result
    
    def _parse_date_time(self, time_text: str) -> int:
        """
        解析日期时间为13位时间戳
        支持格式: "2024年8月21日", "2024-08-21", "2024/08/21"
        """
        now = datetime.now()
        
        try:
            time_text = time_text.strip()
            
            # 格式1: "2024年8月21日"
            date_match = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', time_text)
            if date_match:
                year = int(date_match.group(1))
                month = int(date_match.group(2))
                day = int(date_match.group(3))
                target_time = datetime(year, month, day, 12, 0, 0)
                return int(target_time.timestamp() * 1000)
            
            # 格式2: "2024-08-21" 或 "2024/08/21"
            date_match2 = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', time_text)
            if date_match2:
                year = int(date_match2.group(1))
                month = int(date_match2.group(2))
                day = int(date_match2.group(3))
                target_time = datetime(year, month, day, 12, 0, 0)
                return int(target_time.timestamp() * 1000)
            
        except Exception as e:
            utils.logger.debug(f"[ToutiaoClient._parse_date_time] 解析失败: {time_text}, {e}")
        
        return int(now.timestamp() * 1000)
