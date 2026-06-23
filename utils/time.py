"""时间工具模块"""
import datetime
import time
import ntplib
from .logger import Logger


class TimeUtils:
    """时间工具类"""
    _use_ntp = False
    _ntp_offset = 0
    
    @staticmethod
    def set_ntp_mode(use_ntp: bool = True) -> None:
        """设置是否使用 NTP 时间"""
        TimeUtils._use_ntp = use_ntp
        if use_ntp:
            TimeUtils._sync_ntp_time()
    
    @staticmethod
    def _sync_ntp_time() -> None:
        """同步 NTP 时间，计算时间偏移"""
        try:
            # 使用阿里云 NTP 服务器
            ntp_client = ntplib.NTPClient()
            response = ntp_client.request('ntp.aliyun.com', version=3)
            ntp_time = response.tx_time
            local_time = time.time()
            TimeUtils._ntp_offset = ntp_time - local_time
            Logger.info(f"NTP 校时成功，时间偏移: {TimeUtils._ntp_offset:.3f}秒")
        except Exception as e:
            Logger.error(f"NTP 校时失败: {e}，将使用本地时间")
            TimeUtils._use_ntp = False
            TimeUtils._ntp_offset = 0
    
    @staticmethod
    def get_current_time() -> float:
        """获取当前时间（支持NTP校时）"""
        if TimeUtils._use_ntp:
            return time.time() + TimeUtils._ntp_offset
        return time.time()
    
    @staticmethod
    def timestamp_to_datetime(timestamp: int) -> str:
        """将时间戳转换为可读的日期时间格式"""
        return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
