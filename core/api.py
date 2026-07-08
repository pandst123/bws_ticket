"""哔哩哔哩 API 客户端模块"""
import datetime
import json
import requests
import time
from typing import Dict, Optional
from requests.adapters import HTTPAdapter
from utils.logger import Logger
from utils.cookie import CookieParser
from utils.config import ConfigManager


class BilibiliAPI:
    """哔哩哔哩API客户端"""
    
    BASE_URL = "https://api.bilibili.com/x/activity/bws/online/park/reserve"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/540.36 (KHTML, like Gecko)"
    
    def __init__(self, cookie_string: str):
        self.cookies = CookieParser.parse_cookie_string(cookie_string)
        self._validate_cookies()
        self.csrf_token = self.cookies['bili_jct']
        self.config = ConfigManager.load_config()
        self.session = self._create_session()
    
    def _validate_cookies(self) -> None:
        """验证必要的Cookie是否存在"""
        if 'bili_jct' not in self.cookies:
            raise ValueError("Cookie中缺少必要的bili_jct字段")
    
    def _create_session(self) -> requests.Session:
        """创建HTTP会话"""
        session = requests.Session()
        pool_size = max(10, int(self.config.get('thread_count', 1)) + 2)
        adapter = HTTPAdapter(
            pool_connections=pool_size,
            pool_maxsize=pool_size,
            max_retries=0,
            pool_block=False
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Connection": "keep-alive",
        })
        session.cookies.update(self.cookies)
        return session

    def _request_timeout(self) -> float:
        """获取默认请求超时时间。"""
        return float(self.config.get('request_timeout', 10))
    
    def get_reservation_info(self, reserve_dates: str = "20260710,20260711,20260712", reserve_type: int = 0) -> Optional[Dict]:
        """获取预约信息
        
        Args:
            reserve_dates: 日期，逗号分隔
            reserve_type: 预约类型，0=活动，1=商品
        """
        url = f"{self.BASE_URL}/info"
        params = {
            "csrf": self.csrf_token,
            "reserve_date": reserve_dates,
            "reserve_type": reserve_type,
            "year": "202601"
        }
        
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self._request_timeout()
            )
            response.raise_for_status()
            result = response.json()
            
            if result['code'] != 0:
                Logger.error(f"API错误: {result['code']} 消息: {result['message']}")
                return None
            return result['data']
        except requests.RequestException as e:
            Logger.error(f"网络请求失败: {e}")
            return None
    
    def get_goods_info(self, reserve_dates: str = "20260710,20260711,20260712") -> Optional[Dict]:
        """获取商品预约信息"""
        return self.get_reservation_info(reserve_dates, reserve_type=1)
    
    def make_reservation(self, ticket_number: str, reservation_id: int) -> Dict:
        """进行预约"""
        prepared_request = self.prepare_reservation_request(ticket_number, reservation_id)
        return self.send_prepared_reservation(prepared_request)

    def prepare_reservation_request(
        self,
        ticket_number: str,
        reservation_id: int
    ) -> requests.PreparedRequest:
        """预构建预约请求，不发送网络请求。"""
        url = f"{self.BASE_URL}/do"
        data = {
            "ticket_no": ticket_number,
            "csrf": self.csrf_token,
            "inter_reserve_id": reservation_id,
            "year": "202601"
        }

        request = requests.Request("POST", url, data=data)
        prepared_request = self.session.prepare_request(request)
        prepared_request._bws_log_data = data
        return prepared_request

    def send_prepared_reservation(
        self,
        prepared_request: requests.PreparedRequest,
        timeout: Optional[float] = None
    ) -> Dict:
        """发送已预构建的预约请求。"""
        send_started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        start_perf = time.perf_counter()

        try:
            response = self.session.send(
                prepared_request,
                timeout=timeout if timeout is not None else self._request_timeout()
            )
            elapsed_ms = (time.perf_counter() - start_perf) * 1000
            Logger.log_to_file_only(
                "预约请求完成 | "
                f"发起时间: {send_started_at} | "
                f"耗时: {elapsed_ms:.1f}ms | "
                f"请求URL: {prepared_request.url} | "
                f"请求数据: {getattr(prepared_request, '_bws_log_data', {})}"
            )

            # 检查 HTTP 412 状态码
            if response.status_code == 412:
                error_result = {"code": 412, "message": "[412] IP 或账号被限流，建议更换 IP 再试"}
                Logger.log_to_file_only(f"HTTP 412: IP 或账号被限流", 'WARNING')
                return error_result
            
            response.raise_for_status()
            result = response.json()
            
            # 记录响应正文内容（仅写入文件）
            Logger.log_to_file_only(f"响应正文内容: {json.dumps(result, ensure_ascii=False)}")
            
            return result
        except requests.RequestException as e:
            error_result = {"code": -1, "message": f"网络请求失败: {e}"}
            Logger.log_to_file_only(f"网络请求失败: {e}", 'ERROR')
            return error_result

    def prewarm_reservation_info(
        self,
        reserve_dates: str = "20260710,20260711,20260712",
        timeout: Optional[float] = None
    ) -> bool:
        """使用安全的预约信息 GET 接口预热连接，不触发预约请求。"""
        url = f"{self.BASE_URL}/info"
        params = {
            "csrf": self.csrf_token,
            "reserve_date": reserve_dates,
            "reserve_type": 0,
            "year": "202601"
        }

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=timeout if timeout is not None else self._request_timeout()
            )
            return response.status_code < 500
        except requests.RequestException as e:
            Logger.log_to_file_only(f"预热请求失败: {e}", 'WARNING')
            return False
    
    def get_my_reservations(self) -> Optional[Dict]:
        """获取我的预约信息"""
        url = "https://api.bilibili.com/x/activity/bws/online/park/myreserve"
        params = {
            "csrf": self.csrf_token,
            "year": "202601"
        }
        
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self._request_timeout()
            )
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
