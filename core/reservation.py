"""预约业务模块"""
import datetime
import time
import threading
from typing import Dict, List, Optional, Tuple, Set
from rich.console import Console
from rich.table import Table
from utils.logger import Logger
from utils.time import TimeUtils
from utils.config import ConfigManager
from core.api import BilibiliAPI


class ReservationData:
    """预约数据管理类"""
    
    def __init__(self, reservation_info: Dict, my_reservations: Optional[Dict] = None):
        self.raw_data = reservation_info
        self.my_reservations = my_reservations
        self.ticket_days = list(reservation_info['user_reserve_info'].keys())
        self.ticket_mapping = self._build_ticket_mapping()
        self.activity_mapping = self._build_activity_mapping()
        self.reserved_activity_ids = self._build_reserved_activity_mapping()
    
    def _build_ticket_mapping(self) -> Dict[str, str]:
        """构建日期到票号的映射"""
        return {day: self.raw_data['user_ticket_info'][day]['ticket'] 
                for day in self.ticket_days}
    
    def _build_activity_mapping(self) -> Dict[int, Tuple[str, int, int, bool, int]]:
        """构建活动ID到活动信息的映射，包含VIP优先购信息"""
        activity_map = {}
        for day in self.ticket_days:
            for activity in self.raw_data['reserve_list'][day]:
                activity_id = activity['reserve_id']
                title = activity['act_title'].replace('\n', '')
                start_time = activity['act_begin_time']
                reserve_time = activity['reserve_begin_time']
                is_vip_ticket = activity.get('is_vip_ticket', 0) == 1
                next_reserve = activity.get('next_reserve') or {}
                next_reserve_time = int(next_reserve.get('reserve_begin_time') or 0)
                activity_map[activity_id] = (title, start_time, reserve_time, is_vip_ticket, next_reserve_time)
        return activity_map
    
    def _build_reserved_activity_mapping(self) -> Set[int]:
        """构建用户已预约活动ID的集合"""
        reserved_ids = set()
        if self.my_reservations and 'reserve_list' in self.my_reservations:
            for date_activities in self.my_reservations['reserve_list'].values():
                for activity in date_activities:
                    reserved_ids.add(activity['reserve_id'])
        return reserved_ids
    
    def is_user_vip_for_date(self, date: str) -> bool:
        """检查用户在指定日期是否为VIP"""
        if date not in self.raw_data.get('user_ticket_info', {}):
            return False
        ticket_info = self.raw_data['user_ticket_info'][date]
        return bool(ticket_info.get('is_vip', False))
    
    def get_effective_reserve_time(self, activity_id: int, date: str) -> int:
        """获取有效的预约开始时间，根据用户VIP状态决定"""
        if activity_id not in self.activity_mapping:
            return 0
        
        title, start_time, reserve_time, is_vip_ticket, next_reserve_time = self.activity_mapping[activity_id]
        
        # 如果是VIP优先场次，根据用户VIP状态决定时间
        if is_vip_ticket:
            if self.is_user_vip_for_date(date):
                # VIP用户使用VIP时间
                return reserve_time
            else:
                # 非VIP用户使用普通时间（如果有）
                if next_reserve_time > 0:
                    return next_reserve_time
                return reserve_time
        
        # 非VIP优先场次，直接返回预约时间
        return reserve_time
    
    def is_vip_priority_activity(self, activity_id: int) -> bool:
        """检查活动是否为VIP优先购场次"""
        if activity_id not in self.activity_mapping:
            return False
        _, _, _, is_vip_ticket, _ = self.activity_mapping[activity_id]
        return is_vip_ticket
    
    def display_ticket_info(self) -> None:
        """显示购票信息"""
        Logger.info("当前账号 BW 购票信息：")
        
        # 创建表格
        console = Console()
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("活动名称", style="cyan")
        table.add_column("票种", style="green")
        table.add_column("电子票号", style="yellow")
        
        # 添加数据
        for day in self.ticket_days:
            ticket_info = self.raw_data['user_ticket_info'][day]
            table.add_row(
                ticket_info['screen_name'],
                ticket_info['sku_name'],
                ticket_info['ticket']
            )
        
        # 直接打印表格
        console.print()
        console.print(table)
    
    def display_activities(self) -> None:
        """显示活动信息"""
        # 加载配置
        config = ConfigManager.load_config()
        hide_ended = config.get('activity_filter', {}).get('hide_ended_reservations', False)
        
        # 创建表格
        console = Console()
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("ID", style="cyan")
        table.add_column("活动名称", style="green")
        table.add_column("预约时间", style="yellow")
        table.add_column("开始时间", style="blue")
        
        # 添加数据
        filtered_count = 0
        for day in self.ticket_days:
            for activity in self.raw_data['reserve_list'][day]:
                activity_id = activity['reserve_id']
                
                # 检查是否需要过滤已结束预约的活动或用户已预约的活动
                if hide_ended and (activity.get('state') == 3 or activity_id in self.reserved_activity_ids):
                    filtered_count += 1
                    continue
                title = activity['act_title'].replace('\n', '')
                
                # 使用新的方法获取有效的预约时间
                effective_reserve_time = self.get_effective_reserve_time(activity_id, day)
                reserve_time_str = TimeUtils.timestamp_to_datetime(effective_reserve_time)
                start_time_str = TimeUtils.timestamp_to_datetime(activity['act_begin_time'])
                
                # 检查是否为VIP优先购场次
                if self.is_vip_priority_activity(activity_id):
                    if self.is_user_vip_for_date(day):
                        title = f"[yellow][VIP 优先购] [/yellow]{title}"
                    else:
                        title = f"[cyan][VIP 优先购] [/cyan]{title}"
                
                # 检查是否为二次付费活动
                if '预约只是签售资格，现场签售需购买up主周边。' in activity['describe_info']:
                    title = f"[red][需付费] [/red]{title}"
                
                table.add_row(
                    str(activity_id),
                    title,
                    reserve_time_str,
                    start_time_str
                )
        
        # 直接打印表格
        console.print()
        console.print(table)
        console.print()
        
        if hide_ended and filtered_count > 0:
            console.print(f"已屏蔽 {filtered_count} 个已结束预约或已预约的活动")
    
    def display_activities_for_date(self, selected_date: str) -> None:
        """显示指定日期的活动信息"""
        if selected_date not in self.raw_data['reserve_list']:
            Logger.error(f"未找到日期 {selected_date} 的活动信息")
            return
        
        # 加载配置
        config = ConfigManager.load_config()
        hide_ended = config.get('activity_filter', {}).get('hide_ended_reservations', False)
        
        ticket_info = self.raw_data['user_ticket_info'][selected_date]
        
        # 显示票务信息表格
        console = Console()
        ticket_table = Table(show_header=True, header_style="bold magenta", box=None)
        ticket_table.add_column("活动名称", style="cyan")
        ticket_table.add_column("票种", style="green")
        ticket_table.add_column("电子票号", style="yellow")
        
        ticket_table.add_row(
            ticket_info['screen_name'],
            ticket_info['sku_name'],
            ticket_info['ticket']
        )
        
        console.print()
        Logger.info("票务信息：")
        console.print(ticket_table)
        
        # 准备活动信息表格数据
        activities = self.raw_data['reserve_list'][selected_date]
        activity_data = []
        filtered_count = 0
        
        for activity in activities:
            activity_id = activity['reserve_id']
            
            # 检查是否需要过滤已结束预约的活动或用户已预约的活动
            if hide_ended and (activity.get('state') == 3 or activity_id in self.reserved_activity_ids):
                filtered_count += 1
                continue
            title = activity['act_title'].replace('\n', '')
            
            # 使用新的方法获取有效的预约时间
            effective_reserve_time = self.get_effective_reserve_time(activity_id, selected_date)
            reserve_time_str = TimeUtils.timestamp_to_datetime(effective_reserve_time)
            start_time_str = TimeUtils.timestamp_to_datetime(activity['act_begin_time'])
            
            # 检查是否为VIP优先购场次
            if self.is_vip_priority_activity(activity_id):
                if self.is_user_vip_for_date(selected_date):
                    title = f"[yellow][VIP 优先购] [/yellow]{title}"
                else:
                    title = f"[cyan][VIP 优先购] [/cyan]{title}"
            
            # 检查是否为二次付费活动
            if '预约只是签售资格，现场签售需购买up主周边。' in activity['describe_info']:
                title = f"[red][需付费] [/red]{title}"
            
            # 处理活动提示信息，直接在活动名称中换行显示，设置描述文字为白色
            warning = activity['describe_info'].replace('\n', ' ')[:50] + ('...' if len(activity['describe_info']) > 50 else '')
            title_with_warning = f"{title}\n[white]{warning}[/white]"
            
            activity_data.append([
                activity_id,
                title_with_warning,
                reserve_time_str,
                start_time_str
            ])
        
        # 显示活动信息表格
        activity_table = Table(show_header=True, header_style="bold magenta", box=None)
        activity_table.add_column("ID", style="cyan")
        activity_table.add_column("活动名称", style="green")
        activity_table.add_column("预约时间", style="yellow")
        activity_table.add_column("开始时间", style="blue")
        
        for data in activity_data:
            activity_table.add_row(
                str(data[0]),
                data[1],
                data[2],
                data[3]
            )
        
        console.print()
        Logger.info("活动信息：")
        console.print(activity_table)
        console.print()
        
        if hide_ended and filtered_count > 0:
            console.print(f"已屏蔽 {filtered_count} 个已结束预约或已预约的活动")
    
    def get_ticket_for_activity(self, activity_id: int) -> Optional[str]:
        """根据活动ID获取对应的票号"""
        if activity_id not in self.activity_mapping:
            return None
        
        activity_start_time = self.activity_mapping[activity_id][1]
        activity_date = datetime.datetime.fromtimestamp(activity_start_time).strftime("%Y%m%d")
        return self.ticket_mapping.get(activity_date)
    
    @staticmethod
    def display_my_reservations(my_reservations_data: Dict) -> None:
        """显示我的预约信息"""
        if not my_reservations_data or 'reserve_list' not in my_reservations_data:
            Logger.info("暂无预约信息")
            return
        
        reserve_list = my_reservations_data['reserve_list']
        if not reserve_list:
            Logger.info("暂无预约信息")
            return
        
        Logger.info("我的预约信息：")
        
        # 创建表格
        console = Console()
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("日期", style="cyan")
        table.add_column("活动名称", style="green")
        table.add_column("预约号", style="yellow")
        table.add_column("活动时间", style="blue")
        table.add_column("地点", style="magenta")
        table.add_column("状态", style="red")
        
        # 按日期排序并添加数据
        for date in sorted(reserve_list.keys()):
            activities = reserve_list[date]
            for activity in activities:
                activity_title = activity['act_title'].replace('\n', '')
                
                # 检查是否为二次付费活动
                if '预约只是签售资格，现场签售需购买up主周边。' in activity['describe_info']:
                    activity_title = f"[red][需付费] [/red]{activity_title}"
                
                reserve_no = f"#{activity['reserve_no']}"
                act_time = f"{TimeUtils.timestamp_to_datetime(activity['act_begin_time'])} - {TimeUtils.timestamp_to_datetime(activity['act_end_time'])}"
                location = activity.get('reserve_location', '未知')
                
                # 根据活动类型显示状态
                if activity.get('is_checked') == 1:
                    status = "[green]已签到[/green]"
                elif activity.get('online_state') == 0:
                    status = "[yellow]预约成功[/yellow]"
                else:
                    status = "[blue]待确认[/blue]"
                
                table.add_row(
                    date,
                    activity_title,
                    reserve_no,
                    act_time,
                    location,
                    status
                )
        
        # 直接打印表格
        console.print()
        console.print(table)
        console.print()
        
        # 显示统计信息
        total_count = sum(len(activities) for activities in reserve_list.values())
        Logger.info(f"总计预约活动数量：{total_count} 个")


class ReservationBot:
    """预约机器人"""
    
    def __init__(self, api_client: BilibiliAPI, reservation_data: ReservationData):
        self.api_client = api_client
        self.reservation_data = reservation_data
        self.config = ConfigManager.load_config()
    
    def wait_and_reserve(self, activity_id: int, date: str, mode: str = "scheduled") -> Optional[Dict]:
        """等待并进行预约
        
        Args:
            activity_id: 活动ID
            date: 活动日期
            mode: 预约模式 ('scheduled' 准时开抢, 'immediate' 直接开抢)
            
        Returns:
            预约结果字典，失败时返回 None
        """
        activity_info = self.reservation_data.activity_mapping[activity_id]
        activity_title = activity_info[0]
        
        # 获取有效的预约时间（根据用户VIP状态）
        reserve_time = self.reservation_data.get_effective_reserve_time(activity_id, date)
        
        ticket_number = self.reservation_data.get_ticket_for_activity(activity_id)
        if not ticket_number:
            Logger.error(f"无法找到活动 {activity_id} 对应的票号")
            return None
        
        # 显示VIP优先购信息
        if self.reservation_data.is_vip_priority_activity(activity_id):
            if self.reservation_data.is_user_vip_for_date(date):
                Logger.info(f"活动 {activity_id} 为 [VIP 优先购] 场次，您是VIP用户，将使用VIP开抢时间")
            else:
                Logger.info(f"活动 {activity_id} 为 [VIP 优先购] 场次，您不是VIP用户，将使用普通开抢时间")
        
        if mode == "immediate":
            Logger.info("当前为立即开抢模式，即将开始抢票！")
            return self._start_reservation_loop(ticket_number, activity_id, activity_title)
        else:
            Logger.info("当前为准时开抢模式，等待预约时间...")
            return self._wait_for_reservation_time(ticket_number, activity_id, activity_title, reserve_time, date)
    
    def _wait_for_reservation_time(
        self,
        ticket_number: str,
        activity_id: int,
        activity_title: str,
        reserve_time: int,
        date: str
    ) -> Optional[Dict]:
        """等待预约时间到达
        
        Returns:
            预约结果字典，失败时返回 None
        """
        last_status_time = 0
        completed_auto_sync_checkpoints = set()
        prewarm_done = False
        refresh_prewarm_done = False
        entered_silent_countdown = False
        silent_countdown_seconds = 5.0
        final_spin_seconds = 0.02
        prepared_request = self.api_client.prepare_reservation_request(ticket_number, activity_id)
        time_config = self.config.get('time_calibration', {})
        prewarm_config = self.config.get('request_prewarm', {})
        if not isinstance(time_config, dict):
            time_config = {}
        if not isinstance(prewarm_config, dict):
            prewarm_config = {}
        auto_sync_before = float(time_config.get('auto_sync_before_seconds', 300))
        checkpoint_values = time_config.get('auto_sync_checkpoints_seconds')
        if isinstance(checkpoint_values, list) and checkpoint_values:
            auto_sync_checkpoints = []
            for checkpoint in checkpoint_values:
                if isinstance(checkpoint, (int, float)) and checkpoint > silent_countdown_seconds:
                    auto_sync_checkpoints.append(float(checkpoint))
            auto_sync_checkpoints = sorted(set(auto_sync_checkpoints), reverse=True)
        else:
            auto_sync_checkpoints = [auto_sync_before]
        force_ntp_threshold = float(time_config.get('force_ntp_threshold_seconds', 0.7))
        prewarm_enabled = bool(prewarm_config.get('enabled', True))
        prewarm_before = float(prewarm_config.get('before_seconds', 30))
        refresh_prewarm_before = float(prewarm_config.get('refresh_before_seconds', 5))
        prewarm_timeout = float(prewarm_config.get('timeout_seconds', 1.0))
        prewarm_min_margin = float(prewarm_config.get('min_margin_seconds', 2.0))
        delay_ms = self.config.get('pre_delay', {}).get('start_delay_ms', 0)
        target_time = reserve_time + (delay_ms / 1000.0)

        if delay_ms < 0:
            Logger.warning(f"当前设置为提前 {-delay_ms} 毫秒开抢，程序会按该配置执行")

        def format_checkpoint(checkpoint_seconds: float) -> str:
            """格式化自动校时检查点。"""
            if checkpoint_seconds >= 60 and checkpoint_seconds % 60 == 0:
                return f"{int(checkpoint_seconds / 60)} 分钟"
            return f"{checkpoint_seconds:g} 秒"
        
        try:
            while True:
                current_time = TimeUtils.get_current_time()
                remaining_to_target = target_time - current_time
                
                due_checkpoints = [
                    checkpoint
                    for checkpoint in auto_sync_checkpoints
                    if (
                        checkpoint not in completed_auto_sync_checkpoints
                        and remaining_to_target <= checkpoint
                    )
                ]

                # 多阶段自动校时，但最后静默倒计时阶段不再发起 NTP 请求。
                if due_checkpoints and remaining_to_target > silent_countdown_seconds:
                    checkpoint = min(due_checkpoints)
                    for due_checkpoint in due_checkpoints:
                        completed_auto_sync_checkpoints.add(due_checkpoint)
                    Logger.info(f"开抢前 {format_checkpoint(checkpoint)}，正在进行自动 NTP 校时...")

                    use_ntp_before = TimeUtils._use_ntp
                    result = TimeUtils.calibrate(apply_offset=use_ntp_before)
                    if result.success:
                        real_time_diff = result.offset_seconds
                        if abs(real_time_diff) < 1:
                            Logger.info(
                                f"NTP 校时完成，本机时间与NTP服务器时间差："
                                f"{real_time_diff:.3f}秒，"
                                f"采样: {result.sample_count}次，"
                                f"偏移波动: {result.offset_spread_ms:.1f}ms "
                                "(时间同步良好)"
                            )
                        else:
                            Logger.info(
                                f"NTP 校时完成，本机时间与NTP服务器时间差："
                                f"{real_time_diff:.3f}秒，"
                                f"采样: {result.sample_count}次，"
                                f"偏移波动: {result.offset_spread_ms:.1f}ms "
                                "(建议检查系统时间)"
                            )
                        if result.stability_warning:
                            Logger.warning(f"NTP 校时稳定性提示: {result.stability_warning}")

                        if not use_ntp_before:
                            if abs(real_time_diff) > force_ntp_threshold:
                                TimeUtils.apply_calibration(result)
                                Logger.info(
                                    f"本机时间偏差较大({real_time_diff:.3f}秒)，"
                                    "已临时启用 NTP 校时模式以确保抢票时间准确"
                                )
                            else:
                                Logger.info(f"本机时间偏差较小({real_time_diff:.3f}秒)，继续使用本机时间")
                        else:
                            Logger.info(
                                f"已更新 NTP 时间偏移，服务器: {result.server}，"
                                f"往返耗时: {result.round_trip_ms:.1f}ms，"
                                f"采样: {result.sample_count}次，"
                                f"偏移波动: {result.offset_spread_ms:.1f}ms"
                            )
                    else:
                        Logger.warning(f"自动 NTP 校时失败: {result.error}，将使用当前时间模式")

                    current_time = TimeUtils.get_current_time()
                    remaining_to_target = target_time - current_time

                if prewarm_enabled and remaining_to_target > prewarm_min_margin:
                    if not prewarm_done and remaining_to_target <= prewarm_before:
                        prewarm_done = True
                        success = self.api_client.prewarm_reservation_info(date, timeout=prewarm_timeout)
                        if success:
                            Logger.info("已完成安全接口预热（仅 GET 查询接口，未发送预约请求）")
                        else:
                            Logger.warning("安全接口预热失败，将继续按原计划等待开抢")
                    elif (
                        prewarm_done
                        and not refresh_prewarm_done
                        and remaining_to_target <= refresh_prewarm_before
                    ):
                        refresh_prewarm_done = True
                        success = self.api_client.prewarm_reservation_info(date, timeout=prewarm_timeout)
                        Logger.log_to_file_only(
                            f"临近开抢安全预热{'成功' if success else '失败'}（仅 GET 查询接口）"
                        )
                
                # 等待到达目标开抢时间
                if remaining_to_target > 0:
                    remaining_seconds = remaining_to_target

                    # 最后几秒进入静默高精度倒计时，不再输出倒计时或状态日志。
                    if remaining_seconds <= silent_countdown_seconds:
                        entered_silent_countdown = True
                    elif current_time > last_status_time + 3:
                        last_status_time = current_time
                        reserve_time_str = TimeUtils.timestamp_to_datetime(reserve_time)
                        Logger.info(f'等待开票，距离开票时间 {remaining_seconds:.1f} 秒（{reserve_time_str}）')

                    if entered_silent_countdown and remaining_seconds <= final_spin_seconds:
                        target_perf = time.perf_counter() + remaining_seconds
                        while time.perf_counter() < target_perf:
                            pass
                    elif entered_silent_countdown:
                        time.sleep(min(0.005, max(remaining_seconds / 2, 0.001)))
                    else:
                        time.sleep(min(0.2, max(remaining_seconds - silent_countdown_seconds, 0.05)))
                    continue
                
                # 到达目标时间，先发送首个请求，再输出日志，避免临界点日志 IO 阻塞首包。
                first_result = self.api_client.send_prepared_reservation(prepared_request)

                if delay_ms > 0:
                    Logger.info(f"开票时间已到，延迟 {delay_ms} 毫秒后开始抢票...")
                elif delay_ms < 0:
                    Logger.info(f"提前 {-delay_ms} 毫秒开始抢票...")
                else:
                    Logger.info("开票时间已到，开始抢票...")
                first_code = first_result.get("code")

                if first_code == 0:
                    Logger.info("\033[32m首个请求预约成功！\033[0m")
                    return first_result
                if first_code == 412:
                    Logger.warning(first_result.get("message", "[412] IP 或账号被限流，建议更换 IP 再试"))
                    return first_result
                if first_code == 75574:
                    Logger.error("[75574] 预约已被抢空")
                    return first_result
                if first_code == 76674:
                    Logger.error("[76674] 预约已达上限")
                    return first_result
                if first_code == 75637:
                    Logger.info("[75637] 首个请求返回尚未开放，继续重试")
                elif first_code in (-702, 429, 76650, 76651):
                    Logger.warning(f"首个请求返回 {first_code}，继续进入重试循环")
                elif first_code == -1:
                    Logger.error("首个请求网络错误，继续进入重试循环")
                else:
                    Logger.warning(f"首个请求返回未知状态，继续进入重试循环：{first_result}")

                return self._start_reservation_loop(ticket_number, activity_id, activity_title)
        except KeyboardInterrupt:
            Logger.info("用户中断等待")
            return None
    

    def _start_reservation_loop(self, ticket_number: str, activity_id: int, activity_title: str) -> Optional[Dict]:
        """开始预约循环（支持多线程并发）
        
        Returns:
            预约结果字典，失败时返回 None
        """
        # 获取配置
        config = ConfigManager.load_config()
        loop_delay_ms = config.get('loop_delay', {}).get('loop_delay_ms', 50)
        loop_delay_seconds = loop_delay_ms / 1000.0
        thread_count = config.get('thread_count', 1)
        
        # 线程安全的共享状态
        success_flag = threading.Event()
        stop_flag = threading.Event()
        result_lock = threading.Lock()
        success_count = 0
        error_count = 0
        final_result = None  # 保存最终结果
        
        def reservation_worker(thread_id: int) -> Optional[Dict]:
            """单个线程的预约工作函数"""
            nonlocal success_count, error_count, final_result
            
            while not stop_flag.is_set():
                try:
                    # 如果已经有线程成功，停止当前线程
                    if success_flag.is_set():
                        break
                    
                    result = self.api_client.make_reservation(ticket_number, activity_id)
                    
                    code = result.get("code")
                    need_sleep = False
                    sleep_time = 0
                    
                    with result_lock:
                        if code == 0:
                            Logger.info(f"\033[32m[线程{thread_id}] 预约成功！\033[0m")
                            success_count += 1
                            final_result = result
                            success_flag.set()  # 通知所有线程停止
                            return result
                        elif code == 75637:
                            Logger.info(f"[线程{thread_id}] [75637] 尚未开放，请等待预约开始")
                        elif code == -702:
                            Logger.warning(f"[线程{thread_id}] [702] 请求频率太快")
                            error_count += 1
                        elif code == -1:
                            Logger.error(f"[线程{thread_id}] [-1] 网络错误，继续重试")
                            error_count += 1
                        elif code == 412:
                            Logger.warning(f"[线程{thread_id}] {result.get('message', '[412] IP 或账号被限流，建议更换 IP 再试')}")
                            error_count += 1
                            final_result = result
                            stop_flag.set()  # 停止所有线程
                            return result
                        elif code == 429:
                            Logger.warning(f"[线程{thread_id}] [429] 限流，等待稍后重试")
                            error_count += 1
                            need_sleep = True
                            sleep_time = 0.5  # 等待0.5秒后重试
                        elif code == 75574:
                            Logger.error(f"[线程{thread_id}] [75574] 预约已被抢空")
                            final_result = result
                            stop_flag.set()  # 通知所有线程停止
                            return result
                        elif code == 76674:
                            Logger.error(f"[线程{thread_id}] [76674] 预约已达上限")
                            final_result = result
                            stop_flag.set()  # 通知所有线程停止
                            return result
                        elif code == 76650:
                            Logger.warning(f"[线程{thread_id}] [76650] 操作频繁")
                            error_count += 1
                            need_sleep = True
                            sleep_time = 0.1  # 等待0.1秒后重试
                        elif code == 76651:
                            Logger.warning(f"[线程{thread_id}] [76651] 该活动仅限女性预约")
                            error_count += 1
                            need_sleep = True
                            sleep_time = 0.5  # 等待0.5秒后重试
                        else:
                            Logger.warning(f"[线程{thread_id}] 出金了，是新的未知状态，请自行判断：{result}")
                            error_count += 1
                    
                    # 在锁外执行 sleep，避免阻塞其他线程
                    if need_sleep and sleep_time > 0:
                        time.sleep(sleep_time)
                    
                    # 使用配置的开抢中延迟
                    if loop_delay_seconds > 0:
                        time.sleep(loop_delay_seconds)
                        
                except Exception as e:
                    Logger.error(f"[线程{thread_id}] 预约过程中发生错误：{e}")
                    error_count += 1
                    time.sleep(1)
            
            return None
        
        # 根据线程数决定执行方式
        if thread_count <= 1:
            # 单线程模式（原有逻辑）
            Logger.info("单线程模式开始抢票...")
            try:
                final_result = reservation_worker(1)
            except KeyboardInterrupt:
                Logger.info("用户中断抢票")
                stop_flag.set()
        else:
            # 多线程模式
            Logger.info(f"多线程模式开始抢票，线程数：{thread_count}")
            Logger.info("提示：多线程会并发发送请求，可能触发风控，请谨慎使用")
            Logger.info("按 Ctrl+C 可停止抢票")
            
            threads = []
            try:
                # 使用守护线程，主线程结束时子线程也会结束
                for i in range(thread_count):
                    t = threading.Thread(target=reservation_worker, args=(i+1,), daemon=True)
                    threads.append(t)
                    t.start()
                
                # 等待所有线程完成，定期检查 stop_flag
                while not stop_flag.is_set():
                    # 检查是否所有线程都已结束
                    alive_threads = [t for t in threads if t.is_alive()]
                    if not alive_threads:
                        break
                    # 短暂等待，避免忙等
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                Logger.info("\n用户中断抢票")
                stop_flag.set()
                # 等待线程结束
                for t in threads:
                    t.join(timeout=1)
        
        # 显示最终结果
        if success_flag.is_set():
            Logger.info(f"抢票完成！成功次数：{success_count}")
        else:
            Logger.info(f"抢票结束，未成功。错误次数：{error_count}")
