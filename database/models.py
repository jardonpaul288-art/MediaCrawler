# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/database/models.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

from sqlalchemy import create_engine, Column, Integer, Text, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class BilibiliVideo(Base):
    __tablename__ = 'bilibili_video'
    id = Column(Integer, primary_key=True)
    video_id = Column(BigInteger, nullable=False, index=True, unique=True)
    video_url = Column(Text, nullable=False)
    user_id = Column(BigInteger, index=True)
    nickname = Column(Text)
    avatar = Column(Text)
    liked_count = Column(Integer)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    video_type = Column(Text)
    title = Column(Text)
    desc = Column(Text)
    create_time = Column(BigInteger, index=True)
    disliked_count = Column(Text)
    video_play_count = Column(Text)
    video_favorite_count = Column(Text)
    video_share_count = Column(Text)
    video_coin_count = Column(Text)
    video_danmaku = Column(Text)
    video_comment = Column(Text)
    video_cover_url = Column(Text)
    source_keyword = Column(Text, default='')

class BilibiliVideoComment(Base):
    __tablename__ = 'bilibili_video_comment'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    sex = Column(Text)
    sign = Column(Text)
    avatar = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    comment_id = Column(BigInteger, index=True)
    video_id = Column(BigInteger, index=True)
    content = Column(Text)
    create_time = Column(BigInteger)
    sub_comment_count = Column(Text)
    parent_comment_id = Column(String(255))
    like_count = Column(Text, default='0')

class BilibiliUpInfo(Base):
    __tablename__ = 'bilibili_up_info'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True)
    nickname = Column(Text)
    sex = Column(Text)
    sign = Column(Text)
    avatar = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    total_fans = Column(Integer)
    total_liked = Column(Integer)
    user_rank = Column(Integer)
    is_official = Column(Integer)

class BilibiliContactInfo(Base):
    __tablename__ = 'bilibili_contact_info'
    id = Column(Integer, primary_key=True)
    up_id = Column(BigInteger, index=True)
    fan_id = Column(BigInteger, index=True)
    up_name = Column(Text)
    fan_name = Column(Text)
    up_sign = Column(Text)
    fan_sign = Column(Text)
    up_avatar = Column(Text)
    fan_avatar = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)

class BilibiliUpDynamic(Base):
    __tablename__ = 'bilibili_up_dynamic'
    id = Column(Integer, primary_key=True)
    dynamic_id = Column(BigInteger, index=True)
    user_id = Column(String(255))
    user_name = Column(Text)
    text = Column(Text)
    type = Column(Text)
    pub_ts = Column(BigInteger)
    total_comments = Column(Integer)
    total_forwards = Column(Integer)
    total_liked = Column(Integer)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)

class DouyinAweme(Base):
    __tablename__ = 'douyin_aweme'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    sec_uid = Column(String(255))
    short_user_id = Column(String(255))
    user_unique_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    user_signature = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    aweme_id = Column(BigInteger, index=True)
    aweme_type = Column(Text)
    title = Column(Text)
    desc = Column(Text)
    create_time = Column(BigInteger, index=True)
    liked_count = Column(Text)
    comment_count = Column(Text)
    share_count = Column(Text)
    collected_count = Column(Text)
    aweme_url = Column(Text)
    cover_url = Column(Text)
    video_download_url = Column(Text)
    music_download_url = Column(Text)
    note_download_url = Column(Text)
    source_keyword = Column(Text, default='')

class DouyinAwemeComment(Base):
    __tablename__ = 'douyin_aweme_comment'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    sec_uid = Column(String(255))
    short_user_id = Column(String(255))
    user_unique_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    user_signature = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    comment_id = Column(BigInteger, index=True)
    aweme_id = Column(BigInteger, index=True)
    content = Column(Text)
    create_time = Column(BigInteger)
    sub_comment_count = Column(Text)
    parent_comment_id = Column(String(255))
    like_count = Column(Text, default='0')
    pictures = Column(Text, default='')

class DyCreator(Base):
    __tablename__ = 'dy_creator'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    desc = Column(Text)
    gender = Column(Text)
    follows = Column(Text)
    fans = Column(Text)
    interaction = Column(Text)
    videos_count = Column(String(255))

class KuaishouVideo(Base):
    __tablename__ = 'kuaishou_video'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(64))
    nickname = Column(Text)
    avatar = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    video_id = Column(String(255), index=True)
    video_type = Column(Text)
    title = Column(Text)
    desc = Column(Text)
    create_time = Column(BigInteger, index=True)
    liked_count = Column(Text)
    viewd_count = Column(Text)
    video_url = Column(Text)
    video_cover_url = Column(Text)
    video_play_url = Column(Text)
    source_keyword = Column(Text, default='')

class KuaishouVideoComment(Base):
    __tablename__ = 'kuaishou_video_comment'
    id = Column(Integer, primary_key=True)
    user_id = Column(Text)
    nickname = Column(Text)
    avatar = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    comment_id = Column(BigInteger, index=True)
    video_id = Column(String(255), index=True)
    content = Column(Text)
    create_time = Column(BigInteger)
    sub_comment_count = Column(Text)

class WeiboNote(Base):
    __tablename__ = 'weibo_note'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    gender = Column(Text)
    profile_url = Column(Text)
    ip_location = Column(Text, default='')
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    note_id = Column(BigInteger, index=True)
    content = Column(Text)
    create_time = Column(BigInteger, index=True)
    create_date_time = Column(String(255), index=True)
    liked_count = Column(Text)
    comments_count = Column(Text)
    shared_count = Column(Text)
    note_url = Column(Text)
    source_keyword = Column(Text, default='')

class WeiboNoteComment(Base):
    __tablename__ = 'weibo_note_comment'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    gender = Column(Text)
    profile_url = Column(Text)
    ip_location = Column(Text, default='')
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    comment_id = Column(BigInteger, index=True)
    note_id = Column(BigInteger, index=True)
    content = Column(Text)
    create_time = Column(BigInteger)
    create_date_time = Column(String(255), index=True)
    comment_like_count = Column(Text)
    sub_comment_count = Column(Text)
    parent_comment_id = Column(String(255))

class WeiboCreator(Base):
    __tablename__ = 'weibo_creator'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    desc = Column(Text)
    gender = Column(Text)
    follows = Column(Text)
    fans = Column(Text)
    tag_list = Column(Text)

class XhsCreator(Base):
    __tablename__ = 'xhs_creator'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    desc = Column(Text)
    gender = Column(Text)
    follows = Column(Text)
    fans = Column(Text)
    interaction = Column(Text)
    tag_list = Column(Text)

class XhsNote(Base):
    __tablename__ = 'xhs_note'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    note_id = Column(String(255), index=True)
    type = Column(Text)
    title = Column(Text)
    desc = Column(Text)
    video_url = Column(Text)
    time = Column(BigInteger, index=True)
    last_update_time = Column(BigInteger)
    liked_count = Column(Text)
    collected_count = Column(Text)
    comment_count = Column(Text)
    share_count = Column(Text)
    image_list = Column(Text)
    tag_list = Column(Text)
    note_url = Column(Text)
    source_keyword = Column(Text, default='')
    xsec_token = Column(Text)

class XhsNoteComment(Base):
    __tablename__ = 'xhs_note_comment'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    comment_id = Column(String(255), index=True)
    create_time = Column(BigInteger, index=True)
    note_id = Column(String(255))
    content = Column(Text)
    sub_comment_count = Column(Integer)
    pictures = Column(Text)
    parent_comment_id = Column(String(255))
    like_count = Column(Text)

class TiebaNote(Base):
    __tablename__ = 'tieba_note'
    id = Column(Integer, primary_key=True)
    note_id = Column(String(644), index=True)
    title = Column(Text)
    desc = Column(Text)
    note_url = Column(Text)
    publish_time = Column(String(255), index=True)
    user_link = Column(Text, default='')
    user_nickname = Column(Text, default='')
    user_avatar = Column(Text, default='')
    tieba_id = Column(String(255), default='')
    tieba_name = Column(Text)
    tieba_link = Column(Text)
    total_replay_num = Column(Integer, default=0)
    total_replay_page = Column(Integer, default=0)
    ip_location = Column(Text, default='')
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    source_keyword = Column(Text, default='')

class TiebaComment(Base):
    __tablename__ = 'tieba_comment'
    id = Column(Integer, primary_key=True)
    comment_id = Column(String(255), index=True)
    parent_comment_id = Column(String(255), default='')
    content = Column(Text)
    user_link = Column(Text, default='')
    user_nickname = Column(Text, default='')
    user_avatar = Column(Text, default='')
    tieba_id = Column(String(255), default='')
    tieba_name = Column(Text)
    tieba_link = Column(Text)
    publish_time = Column(String(255), index=True)
    ip_location = Column(Text, default='')
    sub_comment_count = Column(Integer, default=0)
    note_id = Column(String(255), index=True)
    note_url = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)

class TiebaCreator(Base):
    __tablename__ = 'tieba_creator'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(64))
    user_name = Column(Text)
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    gender = Column(Text)
    follows = Column(Text)
    fans = Column(Text)
    registration_duration = Column(Text)

class ZhihuContent(Base):
    __tablename__ = 'zhihu_content'
    id = Column(Integer, primary_key=True)
    content_id = Column(String(64), index=True)
    content_type = Column(Text)
    content_text = Column(Text)
    content_url = Column(Text)
    question_id = Column(String(255))
    title = Column(Text)
    desc = Column(Text)
    created_time = Column(String(32), index=True)
    updated_time = Column(Text)
    voteup_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    source_keyword = Column(Text)
    user_id = Column(String(255))
    user_link = Column(Text)
    user_nickname = Column(Text)
    user_avatar = Column(Text)
    user_url_token = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)

    # persist-1<persist1@126.com>
    # Reason: Fixed ORM model definition error, ensuring consistency with database table structure.
    # Side effects: None
    # Rollback strategy: Restore this line

class ZhihuComment(Base):
    __tablename__ = 'zhihu_comment'
    id = Column(Integer, primary_key=True)
    comment_id = Column(String(64), index=True)
    parent_comment_id = Column(String(64))
    content = Column(Text)
    publish_time = Column(String(32), index=True)
    ip_location = Column(Text)
    sub_comment_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    dislike_count = Column(Integer, default=0)
    content_id = Column(String(64), index=True)
    content_type = Column(Text)
    user_id = Column(String(64))
    user_link = Column(Text)
    user_nickname = Column(Text)
    user_avatar = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)

class ZhihuCreator(Base):
    __tablename__ = 'zhihu_creator'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(64), unique=True, index=True)
    user_link = Column(Text)
    user_nickname = Column(Text)
    user_avatar = Column(Text)
    url_token = Column(Text)
    gender = Column(Text)
    ip_location = Column(Text)
    follows = Column(Integer, default=0)
    fans = Column(Integer, default=0)
    anwser_count = Column(Integer, default=0)
    video_count = Column(Integer, default=0)
    question_count = Column(Integer, default=0)
    article_count = Column(Integer, default=0)
    column_count = Column(Integer, default=0)
    get_voteup_count = Column(Integer, default=0)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)


# ==================== 天津联通舆情监控表 ====================

class UnifiedSentiment(Base):
    """统一舆情表 - 整合各平台帖子和评论数据"""
    __tablename__ = 'unified_sentiment'
    id = Column(Integer, primary_key=True)
    platform = Column(String(32), index=True)           # 平台代码：xhs/dy/ks/bili/wb/tieba/zhihu
    platform_name = Column(String(32), default='')      # 平台中文名：小红书/抖音/快手/B站/微博/贴吧/知乎
    content_type = Column(String(16), index=True)       # 类型：post/comment
    content_id = Column(String(255), index=True)        # 原始内容ID
    title = Column(Text)                                # 标题
    content = Column(Text)                              # 正文内容
    user_nickname = Column(Text)                        # 用户昵称
    user_id = Column(String(255))                       # 用户ID
    ip_location = Column(Text, default='')              # IP归属地（如：天津、北京等）
    source_url = Column(Text)                           # 原始链接
    source_keyword = Column(Text)                       # 搜索关键词
    publish_time = Column(BigInteger, index=True)       # 发布时间戳
    add_ts = Column(BigInteger)                         # 入库时间
    last_modify_ts = Column(BigInteger)                 # 更新时间
    is_analyzed = Column(Integer, default=0, index=True)  # 是否已分析：0-未分析，1-已分析


class NegativeSentiment(Base):
    """负面舆情表 - 存储情感分析判定为负面的内容"""
    __tablename__ = 'negative_sentiment'
    id = Column(Integer, primary_key=True)
    unified_id = Column(Integer, index=True)            # 关联 unified_sentiment.id
    platform = Column(String(32), index=True)           # 平台代码
    platform_name = Column(String(32), default='')      # 平台中文名
    content_type = Column(String(16))                   # 类型：帖子/评论
    title = Column(Text)                                # 标题
    content = Column(Text)                              # 正文内容
    user_nickname = Column(Text)                        # 用户昵称
    ip_location = Column(Text, default='')              # IP归属地
    source_url = Column(Text)                           # 原始链接
    publish_time = Column(BigInteger, index=True)       # 发布时间戳
    last_modify_ts = Column(BigInteger)                 # 最后发言时间
    sentiment_score = Column(String(32))                # 情感得分：正面/中性/负面
    sentiment_reason = Column(Text)                     # 判定原因
    add_ts = Column(BigInteger)                         # 入库时间


# ==================== 今日头条 ====================

class ToutiaoPost(Base):
    """今日头条帖子表"""
    __tablename__ = 'toutiao_post'
    id = Column(Integer, primary_key=True)
    post_id = Column(String(255), nullable=False, index=True, unique=True)  # 帖子ID
    title = Column(Text)                                # 标题
    content = Column(Text)                              # 内容摘要
    source = Column(Text)                               # 来源/作者
    source_url = Column(Text)                           # 原始链接
    image_url = Column(Text)                            # 封面图片
    create_time = Column(BigInteger, index=True)        # 发布时间戳
    add_ts = Column(BigInteger)                         # 入库时间
    last_modify_ts = Column(BigInteger)                 # 更新时间
    source_keyword = Column(Text, default='')           # 搜索关键词


# ==================== 黑猫投诉 ====================

class HeimaoComplaint(Base):
    """黑猫投诉表"""
    __tablename__ = 'heimao_complaint'
    id = Column(Integer, primary_key=True)
    complaint_id = Column(String(255), nullable=False, index=True, unique=True)  # 投诉ID
    title = Column(Text)                                # 投诉标题
    content = Column(Text)                              # 投诉内容
    user_nickname = Column(Text)                        # 投诉用户昵称
    target_company = Column(Text)                       # 被投诉商家
    complaint_status = Column(String(32))               # 处理状态：已回复/已完成/处理中等
    source_url = Column(Text)                           # 原始链接
    create_time = Column(BigInteger, index=True)        # 投诉时间戳
    add_ts = Column(BigInteger)                         # 入库时间
    last_modify_ts = Column(BigInteger)                 # 更新时间
    source_keyword = Column(Text, default='')           # 搜索关键词
