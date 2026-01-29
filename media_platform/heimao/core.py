# -*- coding: utf-8 -*-
"""
黑猫投诉爬虫核心逻辑 - 参考小红书实现
"""
import asyncio
import os
from typing import Dict, List, Optional

from playwright.async_api import (
    BrowserContext,
    BrowserType,
    Page,
    Playwright,
    async_playwright,
)

import config
from base.base_crawler import AbstractCrawler
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store import heimao as heimao_store
from tools import utils
from tools.cdp_browser import CDPBrowserManager
from var import crawler_type_var, source_keyword_var

from .client import HeimaoClient
from .login import HeimaoLogin


class HeimaoCrawler(AbstractCrawler):
    """黑猫投诉爬虫 - 参考小红书架构"""
    
    context_page: Page
    heimao_client: HeimaoClient
    browser_context: BrowserContext
    cdp_manager: Optional[CDPBrowserManager]
    
    def __init__(self):
        self.index_url = "https://tousu.sina.com.cn/index.php"
        self.search_url = "https://tousu.sina.com.cn/index/search/"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.cdp_manager = None
        self.ip_proxy_pool = None
        # 黑猫投诉只搜索"天津联通"
        self.keywords = ["天津联通"]
    
    async def start(self):
        """启动爬虫"""
        playwright_proxy_format, httpx_proxy_format = None, None
        if config.ENABLE_IP_PROXY:
            self.ip_proxy_pool = await create_ip_pool(config.IP_PROXY_POOL_COUNT, enable_validate_ip=True)
            ip_proxy_info: IpInfoModel = await self.ip_proxy_pool.get_proxy()
            playwright_proxy_format, httpx_proxy_format = utils.format_proxy_info(ip_proxy_info)
        
        async with async_playwright() as playwright:
            # 选择启动模式（参考小红书）
            if config.ENABLE_CDP_MODE:
                utils.logger.info("[HeimaoCrawler] 使用CDP模式启动浏览器")
                self.browser_context = await self.launch_browser_with_cdp(
                    playwright,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.CDP_HEADLESS,
                )
            else:
                utils.logger.info("[HeimaoCrawler] 使用标准模式启动浏览器")
                chromium = playwright.chromium
                self.browser_context = await self.launch_browser(
                    chromium,
                    playwright_proxy_format,
                    self.user_agent,
                    headless=config.HEADLESS
                )
                # 加载stealth.js防止被检测
                await self.browser_context.add_init_script(path="libs/stealth.min.js")
            
            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)
            await asyncio.sleep(3)
            
            # 创建API客户端
            self.heimao_client = await self.create_heimao_client(httpx_proxy_format)
            
            # 检查登录状态
            if not await self.heimao_client.pong():
                utils.logger.info("[HeimaoCrawler] 需要登录，启动登录流程...")
                login_obj = HeimaoLogin(
                    login_type=config.LOGIN_TYPE,
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=config.COOKIES,
                )
                await login_obj.begin()
                
                # 登录成功后更新cookies
                await self.heimao_client.update_cookies(browser_context=self.browser_context)
            
            crawler_type_var.set(config.CRAWLER_TYPE)
            if config.CRAWLER_TYPE == "search":
                await self.search()
            else:
                utils.logger.info("[HeimaoCrawler.start] 仅支持search爬取类型")
            
            utils.logger.info("[HeimaoCrawler.start] 黑猫投诉爬虫完成")
    
    async def search(self):
        """搜索爬取（只搜索天津联通）- 支持多页爬取"""
        utils.logger.info("[HeimaoCrawler.search] 开始搜索黑猫投诉")
        
        # 每页返回的结果数（黑猫投诉每页约10条）
        page_size = 10
        start_page = config.START_PAGE
        max_notes = config.CRAWLER_MAX_NOTES_COUNT
        
        for keyword in self.keywords:
            source_keyword_var.set(keyword)
            utils.logger.info(f"[HeimaoCrawler.search] 当前搜索关键词: {keyword}")
            
            page = 1
            total_collected = 0
            
            # 分页循环（参考小红书）
            while (page - start_page + 1) * page_size <= max_notes:
                if page < start_page:
                    utils.logger.info(f"[HeimaoCrawler.search] 跳过第 {page} 页")
                    page += 1
                    continue
                
                try:
                    utils.logger.info(f"[HeimaoCrawler.search] 搜索关键词: {keyword}, 第 {page} 页")
                    
                    # 搜索并获取结果（传入页码）
                    complaints = await self.heimao_client.search_complaints(keyword=keyword, page=page)
                    
                    if not complaints:
                        utils.logger.info(f"[HeimaoCrawler.search] 第 {page} 页没有更多结果，停止翻页")
                        break
                    
                    utils.logger.info(f"[HeimaoCrawler.search] 第 {page} 页获取到 {len(complaints)} 条投诉")
                    
                    for complaint in complaints:
                        # 保存到数据库
                        await heimao_store.update_heimao_complaint(complaint, keyword)
                        total_collected += 1
                    
                    page += 1
                    
                    # 控制请求频率
                    await asyncio.sleep(config.CRAWLER_MAX_SLEEP_SEC)
                    utils.logger.info(f"[HeimaoCrawler.search] 第 {page-1} 页完成，休眠 {config.CRAWLER_MAX_SLEEP_SEC} 秒")
                    
                except Exception as e:
                    utils.logger.error(f"[HeimaoCrawler.search] 第 {page} 页搜索失败: {e}")
                    break
            
            utils.logger.info(f"[HeimaoCrawler.search] 关键词 '{keyword}' 爬取完成，共 {total_collected} 条")
    
    async def create_heimao_client(self, httpx_proxy: Optional[str]) -> HeimaoClient:
        """创建API客户端"""
        utils.logger.info("[HeimaoCrawler.create_heimao_client] 创建黑猫投诉API客户端...")
        cookie_str, cookie_dict = utils.convert_cookies(
            await self.browser_context.cookies(urls=[self.index_url, self.search_url])
        )
        heimao_client_obj = HeimaoClient(
            proxy=httpx_proxy,
            headers={
                "User-Agent": self.user_agent,
                "Cookie": cookie_str,
                "Origin": "https://tousu.sina.com.cn",
                "Referer": "https://tousu.sina.com.cn",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
        return heimao_client_obj
    
    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """启动浏览器（标准模式）"""
        utils.logger.info("[HeimaoCrawler.launch_browser] 创建浏览器上下文...")
        if config.SAVE_LOGIN_STATE:
            user_data_dir = os.path.join(
                os.getcwd(), "browser_data", 
                config.USER_DATA_DIR % config.PLATFORM
            )
            browser_context = await chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                accept_downloads=True,
                headless=headless,
                proxy=playwright_proxy,
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
                channel="chrome",
            )
            return browser_context
        else:
            browser = await chromium.launch(headless=headless, proxy=playwright_proxy, channel="chrome")
            browser_context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent
            )
            return browser_context
    
    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """使用CDP模式启动浏览器（参考小红书）"""
        try:
            self.cdp_manager = CDPBrowserManager()
            browser_context = await self.cdp_manager.launch_and_connect(
                playwright=playwright,
                playwright_proxy=playwright_proxy,
                user_agent=user_agent,
                headless=headless,
            )
            
            # 显示浏览器信息
            browser_info = await self.cdp_manager.get_browser_info()
            utils.logger.info(f"[HeimaoCrawler] CDP浏览器信息: {browser_info}")
            
            return browser_context
            
        except Exception as e:
            utils.logger.error(f"[HeimaoCrawler] CDP模式启动失败，回退到标准模式: {e}")
            chromium = playwright.chromium
            return await self.launch_browser(chromium, playwright_proxy, user_agent, headless)
    
    async def close(self):
        """关闭浏览器"""
        if self.cdp_manager:
            await self.cdp_manager.cleanup()
            self.cdp_manager = None
        else:
            await self.browser_context.close()
        utils.logger.info("[HeimaoCrawler.close] 浏览器已关闭")
