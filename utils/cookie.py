"""Cookie 管理模块"""
import json
import os
import time
from typing import Dict, List, Optional
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
    EXPIRE_SECONDS = 7 * 24 * 3600

    @classmethod
    def get_uid_from_cookie(cls, cookie_string: str) -> Optional[str]:
        """从Cookie中提取B站UID"""
        cookies = CookieParser.parse_cookie_string(cookie_string)
        for key, value in cookies.items():
            if key.lower() == 'dedeuserid' and value:
                return value
        return None
    
    @classmethod
    def _is_expired(cls, timestamp: int) -> bool:
        """检查缓存是否过期"""
        return int(time.time()) - timestamp > cls.EXPIRE_SECONDS
    
    @classmethod
    def _load_cache_data(cls) -> Dict:
        """读取并兼容旧版单账号缓存格式"""
        if not os.path.exists(cls.CACHE_FILE):
            return {"current_uid": None, "accounts": {}}
        
        with open(cls.CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        if 'accounts' in cache_data:
            cache_data.setdefault('current_uid', None)
            return cache_data
        
        cookie_string = cache_data.get('cookie')
        if not cookie_string:
            return {"current_uid": None, "accounts": {}}
        
        uid = cls.get_uid_from_cookie(cookie_string) or "unknown"
        return {
            "current_uid": uid,
            "accounts": {
                uid: {
                    "cookie": cookie_string,
                    "timestamp": cache_data.get('timestamp', 0)
                }
            }
        }
    
    @classmethod
    def _save_cache_data(cls, cache_data: Dict) -> None:
        """写入多账号缓存格式"""
        with open(cls.CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def save_cookie(cls, cookie_string: str) -> Optional[str]:
        """保存Cookie到缓存文件"""
        try:
            uid = cls.get_uid_from_cookie(cookie_string)
            if not uid:
                uid = f"unknown_{int(time.time())}"
                Logger.warning("Cookie 中未找到 DedeUserID，无法用 UID 标识该账号")
            
            cache_data = cls._load_cache_data()
            accounts = cache_data.setdefault('accounts', {})
            accounts[uid] = {
                "cookie": cookie_string,
                "timestamp": int(time.time())
            }
            cache_data['current_uid'] = uid
            cls._save_cache_data(cache_data)
            return uid
        except Exception as e:
            Logger.error(f"保存Cookie缓存失败: {e}")
            return None
    
    @classmethod
    def load_cookie(cls) -> Optional[str]:
        """从缓存文件加载Cookie"""
        current_uid = cls.get_current_uid()
        if not current_uid:
            return None
        return cls.load_cookie_by_uid(current_uid)
    
    @classmethod
    def load_cookie_by_uid(cls, uid: str) -> Optional[str]:
        """按UID加载Cookie"""
        try:
            cache_data = cls._load_cache_data()
            account = cache_data.get('accounts', {}).get(uid)
            if not account:
                return None
            
            if cls._is_expired(account.get('timestamp', 0)):
                Logger.warning(f"UID {uid} 的 Cookie 缓存已过期，需要重新登录")
                cls.remove_cookie(uid)
                return None
            
            return account.get('cookie')
        except Exception as e:
            Logger.error(f"读取 Cookie 缓存失败: {e}")
            return None
    
    @classmethod
    def get_current_uid(cls) -> Optional[str]:
        """获取当前选中的UID"""
        try:
            cache_data = cls._load_cache_data()
            current_uid = cache_data.get('current_uid')
            accounts = cache_data.get('accounts', {})
            if current_uid in accounts:
                return current_uid
            if accounts:
                return next(iter(accounts))
            return None
        except Exception as e:
            Logger.error(f"读取当前账号失败: {e}")
            return None
    
    @classmethod
    def set_current_uid(cls, uid: str) -> bool:
        """切换当前账号"""
        try:
            cache_data = cls._load_cache_data()
            if uid not in cache_data.get('accounts', {}):
                return False
            cache_data['current_uid'] = uid
            cls._save_cache_data(cache_data)
            return True
        except Exception as e:
            Logger.error(f"切换当前账号失败: {e}")
            return False
    
    @classmethod
    def list_accounts(cls) -> List[Dict[str, object]]:
        """列出未过期账号"""
        try:
            cache_data = cls._load_cache_data()
            accounts = cache_data.get('accounts', {})
            current_uid = cache_data.get('current_uid')
            valid_accounts = []
            expired_uids = []
            
            for uid, account in accounts.items():
                if cls._is_expired(account.get('timestamp', 0)):
                    expired_uids.append(uid)
                    continue
                valid_accounts.append({
                    "uid": uid,
                    "cookie": account.get('cookie'),
                    "timestamp": account.get('timestamp', 0),
                    "is_current": uid == current_uid
                })
            
            if expired_uids:
                for uid in expired_uids:
                    accounts.pop(uid, None)
                if cache_data.get('current_uid') in expired_uids:
                    cache_data['current_uid'] = valid_accounts[0]['uid'] if valid_accounts else None
                cls._save_cache_data(cache_data)
            
            return valid_accounts
        except Exception as e:
            Logger.error(f"读取账号列表失败: {e}")
            return []
    
    @classmethod
    def remove_cookie(cls, uid: str) -> None:
        """移除指定UID的Cookie缓存"""
        try:
            cache_data = cls._load_cache_data()
            accounts = cache_data.get('accounts', {})
            accounts.pop(uid, None)
            
            if cache_data.get('current_uid') == uid:
                cache_data['current_uid'] = next(iter(accounts), None)
            
            cls._save_cache_data(cache_data)
        except Exception as e:
            Logger.error(f"移除 UID {uid} 的 Cookie 缓存失败: {e}")
    
    @classmethod
    def clear_cache(cls) -> None:
        """清除缓存文件"""
        try:
            if os.path.exists(cls.CACHE_FILE):
                os.remove(cls.CACHE_FILE)
        except Exception as e:
            Logger.error(f"清除 Cookie 缓存失败: {e}")
