# -*- coding: utf-8 -*-
"""
今日头条登录处理
"""
import asyncio
from typing import Optional

from playwright.async_api import BrowserContext, Page

import config
from base.base_crawler import AbstractLogin
from tools import utils


class ToutiaoLogin(AbstractLogin):
    """今日头条登录类"""
    
    def __init__(
        self,
        login_type: str,
        browser_context: BrowserContext,
        context_page: Page,
        login_phone: str = "",
        cookie_str: str = "",
    ):
        self.login_type = login_type
        self.browser_context = browser_context
        self.context_page = context_page
        self.login_phone = login_phone
        self.cookie_str = cookie_str
    
    async def begin(self):
        """开始登录流程"""
        utils.logger.info("[ToutiaoLogin.begin] 开始今日头条登录流程...")
        
        if self.login_type == "qrcode":
            await self.login_by_qrcode()
        elif self.login_type == "cookie":
            await self.login_by_cookies()
        else:
            raise ValueError(f"不支持的登录类型: {self.login_type}")
    
    async def login_by_qrcode(self):
        """扫码登录"""
        utils.logger.info("[ToutiaoLogin.login_by_qrcode] 请使用今日头条APP扫码登录...")
        
        # 点击登录按钮
        try:
            # 尝试找到登录按钮并点击
            login_btn = await self.context_page.query_selector('text=登录')
            if login_btn:
                await login_btn.click()
                await asyncio.sleep(2)
        except Exception as e:
            utils.logger.warning(f"[ToutiaoLogin.login_by_qrcode] 尝试点击登录按钮失败: {e}")
        
        # 等待用户扫码登录
        max_wait_time = 60 * 3  # 最多等待3分钟
        wait_time = 0
        
        while wait_time < max_wait_time:
            # 检查是否已登录（通过检查页面元素或cookie）
            cookies = await self.browser_context.cookies()
            login_cookies = [c for c in cookies if 'ttwid' in c['name'] or 'passport_csrf_token' in c['name']]
            
            if login_cookies:
                utils.logger.info("[ToutiaoLogin.login_by_qrcode] 登录成功!")
                return
            
            await asyncio.sleep(5)
            wait_time += 5
            utils.logger.info(f"[ToutiaoLogin.login_by_qrcode] 等待扫码登录... ({wait_time}s/{max_wait_time}s)")
        
        raise TimeoutError("扫码登录超时")
    
    async def login_by_mobile(self):
        """手机号登录（暂不实现）"""
        raise NotImplementedError("暂不支持手机号登录")
    
    async def login_by_cookies(self):
        """Cookie登录"""
        utils.logger.info("[ToutiaoLogin.login_by_cookies] 使用Cookie登录...")
        
        if not self.cookie_str:
            raise ValueError("Cookie字符串为空")
        
        # 解析cookie字符串并设置
        for cookie_item in self.cookie_str.split(";"):
            cookie_item = cookie_item.strip()
            if "=" in cookie_item:
                name, value = cookie_item.split("=", 1)
                await self.browser_context.add_cookies([{
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": ".toutiao.com",
                    "path": "/"
                }])
        
        # 刷新页面验证登录
        await self.context_page.reload()
        await asyncio.sleep(3)
        
        utils.logger.info("[ToutiaoLogin.login_by_cookies] Cookie登录完成")
