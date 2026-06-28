"""配置管理模块"""
import json
import os
from typing import Dict, Tuple
from .logger import Logger


class ConfigManager:
    """配置管理器"""
    
    CONFIG_FILE = "bws_config.json"
    DEFAULT_CONFIG = {
        "pre_delay": {
            "start_delay_ms": 0  # 开票前延时（毫秒）
        },
        "loop_delay": {
            "loop_delay_ms": 0  # 开抢中延时（毫秒）
        },
        "retry_intervals": {
            "normal": 0.25,
            "rate_limit": 0.5,
            "not_open": 1.0
        },
        "max_retries": 1000,
        "request_timeout": 10,
        "activity_filter": {
            "hide_ended_reservations": False  # 屏蔽已结束预约活动（state: 3）
        },
        "thread_count": 1  # 并发线程数（默认1）
    }
    
    @classmethod
    def load_config(cls) -> Dict:
        """加载配置"""
        try:
            if os.path.exists(cls.CONFIG_FILE):
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置
                return {**cls.DEFAULT_CONFIG, **config}
            return cls.DEFAULT_CONFIG.copy()
        except Exception as e:
            Logger.warning(f"加载配置失败，使用默认配置: {e}")
            return cls.DEFAULT_CONFIG.copy()
    
    @classmethod
    def save_config(cls, config: Dict) -> None:
        """保存配置"""
        try:
            with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            Logger.error(f"保存配置失败: {e}")
    
    @classmethod
    def validate_config(cls, config: Dict) -> Tuple[bool, str]:
        """验证配置是否合法
        
        Args:
            config: 配置字典
            
        Returns:
            Tuple[bool, str]: (是否合法, 错误信息)
        """
        # 验证开票前延迟设置
        if 'pre_delay' in config:
            delay = config['pre_delay'].get('start_delay_ms', 0)
            if not isinstance(delay, (int, float)):
                return False, "开票前延迟必须是数字"
        
        # 验证开抢中延迟设置
        if 'loop_delay' in config:
            delay = config['loop_delay'].get('loop_delay_ms', 0)
            if not isinstance(delay, (int, float)):
                return False, "开抢中延迟必须是数字"
            if delay < 0:
                return False, "开抢中延迟不能为负数"
        
        # 验证重试间隔
        if 'retry_intervals' in config:
            intervals = config['retry_intervals']
            for key, value in intervals.items():
                if not isinstance(value, (int, float)):
                    return False, f"重试间隔 {key} 必须是数字"
                if value < 0:
                    return False, f"重试间隔 {key} 不能为负数"
        
        # 验证最大重试次数
        if 'max_retries' in config:
            max_retries = config['max_retries']
            if not isinstance(max_retries, int):
                return False, "最大重试次数必须是整数"
            if max_retries < 0:
                return False, "最大重试次数不能为负数"
        
        # 验证请求超时时间
        if 'request_timeout' in config:
            timeout = config['request_timeout']
            if not isinstance(timeout, (int, float)):
                return False, "请求超时时间必须是数字"
            if timeout <= 0:
                return False, "请求超时时间必须大于0"
        
        # 验证活动过滤设置
        if 'activity_filter' in config:
            filter_setting = config['activity_filter']
            if 'hide_ended_reservations' in filter_setting:
                if not isinstance(filter_setting['hide_ended_reservations'], bool):
                    return False, "屏蔽已结束活动设置必须是布尔值"
        
        # 验证线程数设置
        if 'thread_count' in config:
            thread_count = config['thread_count']
            if not isinstance(thread_count, int):
                return False, "线程数必须是整数"
            if thread_count < 1:
                return False, "线程数不能小于1"
            if thread_count > 10:
                return False, "线程数不建议超过10"
        
        return True, ""
