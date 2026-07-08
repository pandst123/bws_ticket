"""时间工具模块"""
import datetime
import math
import statistics
import time
import ntplib
from dataclasses import dataclass
from typing import Dict, List, Optional
from .config import ConfigManager
from .logger import Logger


@dataclass
class TimeCalibrationResult:
    """单次时间校准结果。"""
    success: bool
    server: Optional[str] = None
    offset_seconds: float = 0.0
    round_trip_ms: float = 0.0
    calibrated_at: Optional[float] = None
    applied: bool = False
    sample_count: int = 0
    offset_spread_ms: float = 0.0
    stability_warning: Optional[str] = None
    error: Optional[str] = None


class TimeUtils:
    """时间工具类"""
    _use_ntp = False
    _ntp_offset = 0.0
    _last_calibration: Optional[TimeCalibrationResult] = None

    @staticmethod
    def _get_time_config() -> Dict:
        """获取时间校准配置。"""
        config = ConfigManager.load_config()
        time_config = config.get('time_calibration', {})
        return time_config if isinstance(time_config, dict) else {}

    @staticmethod
    def _get_ntp_servers(time_config: Optional[Dict] = None) -> List[str]:
        """获取 NTP 服务器列表。"""
        if time_config is None:
            time_config = TimeUtils._get_time_config()
        servers = time_config.get('ntp_servers') or []
        if isinstance(servers, str):
            servers = [servers]
        return [server for server in servers if isinstance(server, str) and server.strip()]

    @staticmethod
    def apply_calibration(result: TimeCalibrationResult) -> None:
        """应用已获取的校准偏移到程序内时间。"""
        if not result.success:
            return
        result.applied = True
        TimeUtils._ntp_offset = result.offset_seconds
        TimeUtils._use_ntp = True
        TimeUtils._last_calibration = result
    
    @staticmethod
    def set_ntp_mode(use_ntp: bool = True) -> Optional[TimeCalibrationResult]:
        """设置是否使用 NTP 时间"""
        TimeUtils._use_ntp = use_ntp
        if use_ntp:
            result = TimeUtils.calibrate(apply_offset=True)
            if result.success:
                Logger.info(
                    f"NTP 校时成功，服务器: {result.server}，"
                    f"时间偏移: {result.offset_seconds:.3f}秒，"
                    f"往返耗时: {result.round_trip_ms:.1f}ms，"
                    f"采样: {result.sample_count}次，"
                    f"偏移波动: {result.offset_spread_ms:.1f}ms"
                )
                if result.stability_warning:
                    Logger.warning(f"NTP 校时稳定性提示: {result.stability_warning}")
            else:
                Logger.error(f"NTP 校时失败: {result.error}，将使用本地时间")
            return result
        TimeUtils._ntp_offset = 0.0
        return None
    
    @staticmethod
    def calibrate(apply_offset: bool = True) -> TimeCalibrationResult:
        """校准时间，支持只查看偏差或应用程序内偏移。"""
        time_config = TimeUtils._get_time_config()
        servers = TimeUtils._get_ntp_servers(time_config)
        timeout = float(time_config.get('timeout_seconds', 2.0))
        samples_per_server = max(1, int(time_config.get('samples_per_server', 3)))
        max_successful_samples = max(1, int(time_config.get('max_successful_samples', 5)))
        min_successful_samples = max(1, int(time_config.get('min_successful_samples', 3)))
        max_offset_spread_ms = float(time_config.get('max_offset_spread_ms', 50.0))

        if not servers:
            result = TimeCalibrationResult(
                success=False,
                error="未配置可用的 NTP 服务器"
            )
            TimeUtils._last_calibration = result
            if apply_offset:
                TimeUtils._use_ntp = False
                TimeUtils._ntp_offset = 0.0
            return result

        last_error = None
        samples = []
        for server in servers:
            for _ in range(samples_per_server):
                try:
                    ntp_client = ntplib.NTPClient()
                    start_perf = time.perf_counter()
                    response = ntp_client.request(server, version=3, timeout=timeout)
                    end_perf = time.perf_counter()
                    local_time = time.time()

                    response_delay = getattr(response, 'delay', None)
                    if isinstance(response_delay, (int, float)) and response_delay >= 0:
                        round_trip_ms = response_delay * 1000
                    else:
                        round_trip_ms = (end_perf - start_perf) * 1000

                    # ntplib 的 offset 来自 NTP 四时间戳公式，比 tx_time-local_time 更能抵消网络往返延迟。
                    offset = getattr(response, 'offset', None)
                    if not isinstance(offset, (int, float)):
                        offset = response.tx_time - local_time

                    result = TimeCalibrationResult(
                        success=True,
                        server=server,
                        offset_seconds=float(offset),
                        round_trip_ms=float(round_trip_ms),
                        calibrated_at=local_time,
                        applied=apply_offset
                    )

                    samples.append(result)
                    if len(samples) >= max_successful_samples:
                        break
                except Exception as e:
                    last_error = f"{server}: {e}"
                    continue

            if len(samples) >= max_successful_samples:
                break

        if samples:
            samples_by_delay = sorted(samples, key=lambda item: item.round_trip_ms)
            if len(samples_by_delay) >= min_successful_samples:
                stable_count = max(min_successful_samples, math.ceil(len(samples_by_delay) * 0.6))
                stable_count = min(stable_count, len(samples_by_delay))
            else:
                stable_count = len(samples_by_delay)
            stable_samples = samples_by_delay[:stable_count]
            stable_offsets = [sample.offset_seconds for sample in stable_samples]
            best_delay_sample = samples_by_delay[0]
            offset_spread_ms = (max(stable_offsets) - min(stable_offsets)) * 1000
            stability_warning = None
            if len(stable_samples) < min_successful_samples:
                stability_warning = (
                    f"有效样本不足，当前 {len(stable_samples)} 次，"
                    f"建议至少 {min_successful_samples} 次"
                )
            elif offset_spread_ms > max_offset_spread_ms:
                stability_warning = (
                    f"偏移波动较大({offset_spread_ms:.1f}ms)，"
                    f"超过阈值 {max_offset_spread_ms:.1f}ms"
                )

            result = TimeCalibrationResult(
                success=True,
                server=best_delay_sample.server,
                offset_seconds=float(statistics.median(stable_offsets)),
                round_trip_ms=best_delay_sample.round_trip_ms,
                calibrated_at=time.time(),
                applied=apply_offset,
                sample_count=len(stable_samples),
                offset_spread_ms=offset_spread_ms,
                stability_warning=stability_warning
            )

            TimeUtils._last_calibration = result
            if apply_offset:
                TimeUtils._ntp_offset = result.offset_seconds
                TimeUtils._use_ntp = True
            return result

        result = TimeCalibrationResult(
            success=False,
            error=last_error or "所有 NTP 服务器均不可用"
        )
        TimeUtils._last_calibration = result
        if apply_offset:
            TimeUtils._use_ntp = False
            TimeUtils._ntp_offset = 0.0
        return result
    
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

    @staticmethod
    def get_status() -> Dict:
        """获取当前校时状态。"""
        last = TimeUtils._last_calibration
        return {
            "use_ntp": TimeUtils._use_ntp,
            "mode": "ntp" if TimeUtils._use_ntp else "local",
            "offset_seconds": TimeUtils._ntp_offset,
            "last_success": last.success if last else None,
            "last_server": last.server if last else None,
            "last_offset_seconds": last.offset_seconds if last else None,
            "last_round_trip_ms": last.round_trip_ms if last else None,
            "last_calibrated_at": last.calibrated_at if last else None,
            "last_applied": last.applied if last else None,
            "last_sample_count": last.sample_count if last else None,
            "last_offset_spread_ms": last.offset_spread_ms if last else None,
            "last_stability_warning": last.stability_warning if last else None,
            "last_error": last.error if last else None,
        }
