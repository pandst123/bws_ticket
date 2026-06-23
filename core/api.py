"""哔哩哔哩 API 客户端模块"""
import datetime
import json
import requests
from typing import Dict, Optional
from utils.logger import Logger
from utils.cookie import CookieParser


class BilibiliAPI:
    """哔哩哔哩API客户端"""
    
    BASE_URL = "https://api.bilibili.com/x/activity/bws/online/park/reserve"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/540.36 (KHTML, like Gecko)"
    
    def __init__(self, cookie_string: str):
        self.cookies = CookieParser.parse_cookie_string(cookie_string)
        self._validate_cookies()
        self.csrf_token = self.cookies['bili_jct']
        self.session = self._create_session()
    
    def _validate_cookies(self) -> None:
        """验证必要的Cookie是否存在"""
        if 'bili_jct' not in self.cookies:
            raise ValueError("Cookie中缺少必要的bili_jct字段")
    
    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        session.headers.update({"User-Agent": self.USER_AGENT})
        return session
    
    def get_reservation_info(self, reserve_dates: str = "20250711,20250712,20240713") -> Optional[Dict]:
        """获取预约信息"""
        url = f"{self.BASE_URL}/info"
        params = {
            "csrf": self.csrf_token,
            "reserve_date": reserve_dates
        }
        
        try:
            response = self.session.get(url, params=params, cookies=self.cookies)
            response.raise_for_status()
            result = response.json()
            
            if result['code'] != 0:
                Logger.error(f"API错误: {result['code']} 消息: {result['message']}")
                return None
            return result['data']
        except requests.RequestException as e:
            Logger.error(f"网络请求失败: {e}")
            return None
    
    def make_reservation(self, ticket_number: str, reservation_id: int) -> Dict:
        """进行预约"""
        url = f"{self.BASE_URL}/do"
        data = {
            "ticket_no": ticket_number,
            "csrf": self.csrf_token,
            "inter_reserve_id": reservation_id
        }
        
        # 记录请求发起时间（仅写入文件）
        request_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        Logger.log_to_file_only(f"请求发起时间: {request_time} | 请求URL: {url} | 请求数据: {data}")
        
        try:
            response = self.session.post(url, data=data, cookies=self.cookies)
            response.raise_for_status()
            result = response.json()
            
            # 记录响应正文内容（仅写入文件）
            Logger.log_to_file_only(f"响应正文内容: {json.dumps(result, ensure_ascii=False)}")
            
            return result
        except requests.RequestException as e:
            error_result = {"code": -1, "message": f"网络请求失败: {e}"}
            Logger.log_to_file_only(f"网络请求失败: {e}", 'ERROR')
            return error_result
    
    def get_my_reservations(self) -> Optional[Dict]:
        """获取我的预约信息"""
        url = "https://api.bilibili.com/x/activity/bws/online/park/myreserve"
        params = {
            "csrf": self.csrf_token
        }
        
        try:
            response = self.session.get(url, params=params, cookies=self.cookies)
            response.raise_for_status()
            result = response.json()
            
            if result['code'] != 0:
                Logger.error(f"API错误: {result['code']} 消息: {result['message']}")
                return None
            return result['data']
        except requests.RequestException as e:
            Logger.error(f"网络请求失败: {e}")
            return None
    
    def validate_cookie(self) -> bool:
        """验证Cookie是否有效"""
        try:
            # 尝试获取预约信息来验证Cookie有效性
            result = self.get_reservation_info()
            return result is not None
        except Exception:
            return False
