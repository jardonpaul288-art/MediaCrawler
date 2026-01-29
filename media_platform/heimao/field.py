# -*- coding: utf-8 -*-
"""
黑猫投诉字段定义
"""
from enum import Enum


class ComplaintStatus(Enum):
    """投诉状态"""
    PENDING = "待处理"
    REPLIED = "已回复"
    COMPLETED = "已完成"
