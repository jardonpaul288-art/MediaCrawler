# -*- coding: utf-8 -*-
"""
黑猫投诉API客户端 - 使用网络请求拦截获取API数据
"""
import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import httpx
from playwright.async_api import BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_fixed

from base.base_crawler import AbstractApiClient
from tools import utils


class HeimaoClient(AbstractApiClient):
    """黑猫投诉API客户端"""
    
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
        self._host = "https://tousu.sina.com.cn"
        
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
            await browser_context.cookies(urls=[self._host])
        )
        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict
    
    async def pong(self) -> bool:
        """检查状态"""
        utils.logger.info("[HeimaoClient.pong] 检查黑猫投诉登录状态...")
        return True
    
    async def _handle_response(self, response):
        """处理拦截到的响应"""
        try:
            url = response.url
            # 拦截黑猫投诉的搜索API
            if '/api/index/s' in url or ('tousu.sina.com.cn' in url and 'api' in url):
                try:
                    # 检查响应类型
                    content_type = response.headers.get('content-type', '')
                    if 'json' in content_type or 'javascript' in content_type:
                        # 提取URL中的page参数用于调试
                        page_match = re.search(r'[?&]page=(\d+)', url)
                        page_num = page_match.group(1) if page_match else "unknown"
                        
                        body = await response.body()
                        text = body.decode('utf-8')
                        
                        # 尝试解析JSON
                        if text.startswith('{') or text.startswith('['):
                            data = json.loads(text)
                            utils.logger.info(f"[HeimaoClient] 拦截到API响应(page={page_num}): {url[:100]}...")
                            self._intercepted_data.append({
                                'url': url,
                                'data': data
                            })
                except Exception as e:
                    pass
        except Exception as e:
            pass
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def search_complaints(self, keyword: str = "天津联通", page: int = 1, count: int = 20) -> List[Dict]:
        """
        搜索投诉
        """
        utils.logger.info(f"[HeimaoClient.search_complaints] 搜索关键词: {keyword}, 第 {page} 页")
        
        # 清空拦截数据
        self._intercepted_data = []
        
        try:
            # 注册响应拦截器
            self.playwright_page.on("response", self._handle_response)
            
            # 翻页逻辑
            if page == 1:
                # 第一页直接跳转
                search_url = f"{self._host}/index/search/?keywords={keyword}&t=1&page=1"
                await self.playwright_page.goto(search_url)
            else:
                # 后续页使用滚动加载
                # 1. 确保在搜索页
                if "/index/search" not in self.playwright_page.url:
                    search_url = f"{self._host}/index/search/?keywords={keyword}&t=1&page=1"
                    await self.playwright_page.goto(search_url)
                    await asyncio.sleep(2)
                
                # 2. 滚动到底部触发加载
                utils.logger.info(f"[HeimaoClient] 滚动到底部触发加载: page={page}")
                await self.playwright_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # 3. 稍微等待一下，如果还没触发，尝试再次滚动（有时候一次滚动不够）
                await asyncio.sleep(1)
                await self.playwright_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            # 等待数据加载
            await asyncio.sleep(3)
            
            # 优先从拦截的API数据中解析
            if self._intercepted_data:
                # 过滤出当前页的数据（如果有多个API响应）
                # 简单策略：取最后一个包含数据的响应
                results = self._parse_intercepted_data()
                if results:
                    utils.logger.info(f"[HeimaoClient.search_complaints] 从API拦截获取到 {len(results)} 条结果")
                    return results[:count]
            
            # 回退到DOM解析
            utils.logger.info("[HeimaoClient.search_complaints] API拦截失败，回退到DOM解析")
            results = await self._extract_complaints()
            return results[:count]
            
        except Exception as e:
            utils.logger.error(f"[HeimaoClient.search_complaints] 搜索失败: {e}")
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
        seen_keys = set()
        
        for item in self._intercepted_data:
            try:
                data = item.get('data', {})
                # API结构: result -> data -> lists -> [item]
                # item结构: main -> {title, summary, timestamp, url, ...}
                
                result_data = data.get('result', {}).get('data', {})
                lists = result_data.get('lists', [])
                
                if lists:
                    for complaint in lists:
                        main_info = complaint.get('main', {})
                        author_info = complaint.get('author', {})
                        
                        if not main_info:
                            continue
                            
                        # 去重逻辑
                        complaint_id = main_info.get('sn', '')
                        url = main_info.get('url', '')
                        dedup_key = complaint_id if complaint_id else url
                        
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)
                        
                        title = main_info.get('title', '')
                        summary = main_info.get('summary', '')
                        
                        # 获取时间戳 (10位秒级 -> 13位毫秒级)
                        timestamp = main_info.get('timestamp', 0)
                        publish_time = int(timestamp) * 1000 if timestamp else 0
                        
                        # 格式化时间字符串
                        time_str = ""
                        if publish_time:
                            dt = datetime.fromtimestamp(publish_time / 1000)
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 构建URL
                        if url and not url.startswith('http'):
                            url = f"https:{url}" if url.startswith('//') else f"{self._host}{url}"
                        
                        result = {
                            'title': self._clean_html(title),
                            'content': self._clean_html(summary),
                            'user_nickname': author_info.get('title', ''),
                            'status': str(main_info.get('status', '')),
                            'company': main_info.get('cotitle', ''),
                            'time': time_str,
                            'publish_time': publish_time,
                            'url': url,
                            'complaint_id': complaint_id,
                        }
                        results.append(result)
                        
            except Exception as e:
                utils.logger.debug(f"[HeimaoClient._parse_intercepted_data] 解析失败: {e}")
        
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
    
    async def _extract_complaints(self) -> List[Dict]:
        """从页面提取投诉列表（DOM备选方案）"""
        results = []
        try:
            # 尝试获取所有包含链接的投诉
            items = await self.playwright_page.query_selector_all('.blackcat-list-item, .complaint-item, [class*="tousu-item"]')
            
            for item in items:
                try:
                    result = await self._parse_complaint_item(item)
                    if result and result.get('title'):
                        results.append(result)
                except Exception:
                    continue
        except Exception as e:
            utils.logger.error(f"[HeimaoClient._extract_complaints] 提取失败: {e}")
        return results
    
    async def _parse_complaint_item(self, item) -> Dict:
        """解析单个投诉项（DOM）"""
        result = {
            'title': '', 'content': '', 'user_nickname': '', 
            'status': '', 'company': '', 'time': '', 'url': '', 'publish_time': 0
        }
        try:
            # 标题
            title_el = await item.query_selector('a[class*="title"], .title a')
            if title_el:
                result['title'] = (await title_el.inner_text()).strip()
                href = await title_el.get_attribute('href')
                if href:
                    result['url'] = f"https:{href}" if href.startswith('//') else (f"{self._host}{href}" if href.startswith('/') else href)
            
            # 内容
            content_el = await item.query_selector('[class*="content"], [class*="summary"]')
            if content_el:
                result['content'] = (await content_el.inner_text()).strip()
            
            # 时间
            time_el = await item.query_selector('[class*="time"], [class*="date"]')
            if time_el:
                time_text = (await time_el.inner_text()).strip()
                result['time'] = time_text
                # 尝试解析时间
                try:
                    dt = datetime.strptime(time_text, "%Y-%m-%d %H:%M:%S")
                    result['publish_time'] = int(dt.timestamp() * 1000)
                except:
                    pass
                    
        except Exception:
            pass
        return result
