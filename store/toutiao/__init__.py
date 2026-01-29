# -*- coding: utf-8 -*-
"""
今日头条数据存储模块 - 参考小红书store实现
"""
import json
from typing import Dict, List

from sqlalchemy import select, update

import config
from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import ToutiaoPost
from tools import utils
from tools.time_util import get_current_timestamp
from tools.async_file_writer import AsyncFileWriter
from var import crawler_type_var, source_keyword_var


class ToutiaoStoreFactory:
    """今日头条存储工厂"""
    STORES = {
        "csv": "ToutiaoCsvStoreImplement",
        "db": "ToutiaoDbStoreImplement",
        "postgres": "ToutiaoDbStoreImplement",
        "json": "ToutiaoJsonStoreImplement",
    }
    
    @staticmethod
    def create_store() -> AbstractStore:
        store_type = config.SAVE_DATA_OPTION
        if store_type == "csv":
            return ToutiaoCsvStoreImplement()
        elif store_type in ("db", "postgres"):
            return ToutiaoDbStoreImplement()
        elif store_type == "json":
            return ToutiaoJsonStoreImplement()
        else:
            # 默认使用db存储
            return ToutiaoDbStoreImplement()


class ToutiaoCsvStoreImplement(AbstractStore):
    """CSV存储实现"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="toutiao", crawler_type=crawler_type_var.get())
    
    async def store_content(self, content_item: Dict):
        await self.writer.write_to_csv(item_type="contents", item=content_item)
    
    async def store_comment(self, comment_item: Dict):
        pass  # 今日头条不爬评论
    
    async def store_creator(self, creator_item: Dict):
        pass  # 今日头条不爬创作者


class ToutiaoJsonStoreImplement(AbstractStore):
    """JSON存储实现"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="toutiao", crawler_type=crawler_type_var.get())
    
    async def store_content(self, content_item: Dict):
        await self.writer.write_single_item_to_json(item_type="contents", item=content_item)
    
    async def store_comment(self, comment_item: Dict):
        pass  # 今日头条不爬评论
    
    async def store_creator(self, creator_item: Dict):
        pass  # 今日头条不爬创作者


class ToutiaoDbStoreImplement(AbstractStore):
    """数据库存储实现"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    async def store_content(self, content_item: Dict):
        """存储帖子到数据库"""
        post_id = content_item.get("post_id")
        if not post_id:
            return
        async with get_session() as session:
            if await self._content_exists(session, post_id):
                await self._update_content(session, content_item)
            else:
                await self._add_content(session, content_item)
    
    async def _content_exists(self, session, post_id: str) -> bool:
        """检查帖子是否存在"""
        stmt = select(ToutiaoPost).where(ToutiaoPost.post_id == post_id)
        result = await session.execute(stmt)
        return result.first() is not None
    
    async def _add_content(self, session, content_item: Dict):
        """添加新帖子"""
        current_ts = int(get_current_timestamp())
        # 使用从页面获取的真实发布时间（13位时间戳）
        # 如果没有获取到，则使用当前时间
        publish_time = content_item.get("publish_time", 0)
        if not publish_time or publish_time == 0:
            publish_time = current_ts
        
        post = ToutiaoPost(
            post_id=content_item.get("post_id"),
            title=content_item.get("title", ""),
            content=content_item.get("content", ""),
            source=content_item.get("source", ""),
            source_url=content_item.get("url", ""),
            image_url=content_item.get("image_url", ""),
            create_time=publish_time,    # 使用真实的发布时间
            add_ts=current_ts,           # 添加到数据库的时间
            last_modify_ts=current_ts,   # 最后修改时间
            source_keyword=content_item.get("source_keyword", "")
        )
        session.add(post)
        utils.logger.info(f"[ToutiaoDbStore] 新增帖子: {content_item.get('title', '')[:30]}...")
    
    async def _update_content(self, session, content_item: Dict):
        """更新已有帖子"""
        post_id = content_item.get("post_id")
        current_ts = int(get_current_timestamp())
        update_data = {
            "title": content_item.get("title", ""),
            "content": content_item.get("content", ""),
            "source": content_item.get("source", ""),
            "source_url": content_item.get("url", ""),
            "last_modify_ts": current_ts,
        }
        stmt = update(ToutiaoPost).where(ToutiaoPost.post_id == post_id).values(**update_data)
        await session.execute(stmt)
        utils.logger.info(f"[ToutiaoDbStore] 更新帖子: {content_item.get('title', '')[:30]}...")
    
    async def store_comment(self, comment_item: Dict):
        pass  # 今日头条不爬评论
    
    async def store_creator(self, creator_item: Dict):
        pass  # 今日头条不爬创作者


async def update_toutiao_post(post_data: Dict, keyword: str = "") -> None:
    """
    更新或插入今日头条帖子数据
    
    Args:
        post_data: 帖子数据（包含从页面解析的publish_time）
        keyword: 搜索关键词
    """
    # 生成帖子ID（使用URL的hash作为唯一标识）
    post_url = post_data.get("url", "")
    post_id = str(hash(post_url)) if post_url else str(int(get_current_timestamp() * 1000))
    
    local_db_item = {
        "post_id": post_id,
        "title": post_data.get("title", ""),
        "content": post_data.get("content", ""),
        "source": post_data.get("source", ""),
        "url": post_url,
        "image_url": post_data.get("image_url", ""),
        "source_keyword": keyword or source_keyword_var.get(),
        "publish_time": post_data.get("publish_time", 0),  # 从页面获取的真实发布时间（13位时间戳）
    }
    
    utils.logger.info(f"[store.toutiao.update_toutiao_post] 保存帖子: {local_db_item.get('title', '')[:30]}...")
    await ToutiaoStoreFactory.create_store().store_content(local_db_item)
