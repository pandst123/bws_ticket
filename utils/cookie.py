"""Cookie 管理模块"""
import json
import os
import time
from typing import Dict, Optional
from .logger import Logger


class CookieParser:
    """Cookie解析器"""
    
    @staticmethod
    def parse_cookie_string(cookie_string: str) -> Dict[str, str]:
        """解析Cookie字符串为字典"""
        cookies = {}
        for cookie_item in cookie_string.split(';'):
            if '=' in cookie_item:
                key, value = cookie_item.split('=', 1)
                cookies[key.strip()] = value.strip()
        return cookies


class CookieCache:
    """Cookie缓存管理器"""
    
    CACHE_FILE = "cookie_cache.json"
    
    @classmethod
    def save_cookie(cls, cookie_string: str) -> None:
        """保存Cookie到缓存文件"""
        try:
            cache_data = {
                "cookie": cookie_string,
                "timestamp": int(time.time())
            }
            with open(cls.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            Logger.error(f"保存Cookie缓存失败: {e}")
    
    @classmethod
    def load_cookie(cls) -> Optional[str]:
        """从缓存文件加载Cookie"""
        try:
            if not os.path.exists(cls.CACHE_FILE):
                return None
            
            with open(cls.CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期（7天）
            cache_age = int(time.time()) - cache_data.get('timestamp', 0)
            if cache_age > 7 * 24 * 3600:  # 7天过期
                Logger.warning("Cookie 缓存已过期，需要重新输入")
                return None
            
            return cache_data.get('cookie')
        except Exception as e:
            Logger.error(f"读取 Cookie 缓存失败: {e}")
            return None
    
    @classmethod
    def clear_cache(cls) -> None:
        """清除缓存文件"""
        try:
            if os.path.exists(cls.CACHE_FILE):
                os.remove(cls.CACHE_FILE)
        except Exception as e:
            Logger.error(f"清除 Cookie 缓存失败: {e}")
