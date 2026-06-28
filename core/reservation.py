"""预约业务模块"""
import datetime
import time
import ntplib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    
    def _build_activity_mapping(self) -> Dict[int, Tuple[str, int, int]]:
        """构建活动ID到活动信息的映射"""
        activity_map = {}
        for day in self.ticket_days:
            for activity in self.raw_data['reserve_list'][day]:
                activity_id = activity['reserve_id']
                title = activity['act_title'].replace('\n', '')
                start_time = activity['act_begin_time']
                reserve_time = activity['reserve_begin_time']
                activity_map[activity_id] = (title, start_time, reserve_time)
        return activity_map
    
    def _build_reserved_activity_mapping(self) -> Set[int]:
        """构建用户已预约活动ID的集合"""
        reserved_ids = set()
        if self.my_reservations and 'reserve_list' in self.my_reservations:
            for date_activities in self.my_reservations['reserve_list'].values():
                for activity in date_activities:
                    reserved_ids.add(activity['reserve_id'])
        return reserved_ids
    
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
                reserve_time_str = TimeUtils.timestamp_to_datetime(activity['reserve_begin_time'])
                start_time_str = TimeUtils.timestamp_to_datetime(activity['act_begin_time'])
                
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
            reserve_time_str = TimeUtils.timestamp_to_datetime(activity['reserve_begin_time'])
            start_time_str = TimeUtils.timestamp_to_datetime(activity['act_begin_time'])
            
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
    
    def wait_and_reserve(self, activity_id: int, mode: str = "scheduled") -> Optional[Dict]:
        """等待并进行预约
        
        Args:
            activity_id: 活动ID
            mode: 预约模式 ('scheduled' 准时开抢, 'immediate' 直接开抢)
            
        Returns:
            预约结果字典，失败时返回 None
        """
        activity_info = self.reservation_data.activity_mapping[activity_id]
        activity_title, start_time, reserve_time = activity_info
        
        ticket_number = self.reservation_data.get_ticket_for_activity(activity_id)
        if not ticket_number:
            Logger.error(f"无法找到活动 {activity_id} 对应的票号")
            return None
        
        if mode == "immediate":
            Logger.info("当前为立即开抢模式，即将开始抢票！")
            return self._start_reservation_loop(ticket_number, activity_id, activity_title)
        else:
            Logger.info("当前为准时开抢模式，等待预约时间...")
            return self._wait_for_reservation_time(ticket_number, activity_id, activity_title, reserve_time)
    
    def _wait_for_reservation_time(self, ticket_number: str, activity_id: int, activity_title: str, reserve_time: int) -> Optional[Dict]:
        """等待预约时间到达
        
        Returns:
            预约结果字典，失败时返回 None
        """
        last_status_time = 0
        auto_sync_done = False
        
        while True:
            current_time = int(TimeUtils.get_current_time())
            
            # 开抢前5分钟自动校时
            if not auto_sync_done and current_time >= reserve_time - 300:  # 5分钟 = 300秒
                auto_sync_done = True
                Logger.info("开抢前 5 分钟，正在进行自动 NTP 校时...")
                
                # 记录校时前的时间（如果已启用 NTP 则使用当前 NTP 时间，否则使用本机时间）
                time_before = TimeUtils.get_current_time()
                local_time_before = time.time()  # 始终记录本机时间用于显示真实的本机与NTP差异
                
                # 执行NTP校时
                try:
                    ntp_client = ntplib.NTPClient()
                    response = ntp_client.request('ntp.aliyun.com', version=3)
                    ntp_time = response.tx_time
                    
                    # 计算本机时间与NTP服务器的真实时间差（用于显示）
                    real_time_diff = ntp_time - local_time_before
                    
                    # 计算新的NTP偏移（基于本机时间）
                    new_ntp_offset = ntp_time - local_time_before
                    
                    # 显示本机时间与NTP服务器的真实时间差
                    if abs(real_time_diff) < 1:
                        Logger.info(f"NTP 校时完成，本机时间与NTP服务器时间差：{real_time_diff:.3f}秒 (时间同步良好)")
                    else:
                        Logger.info(f"NTP 校时完成，本机时间与NTP服务器时间差：{real_time_diff:.3f}秒 (建议检查系统时间)")
                    
                    # 如果用户未开启NTP模式，根据时间差决定是否临时应用校时
                    if not TimeUtils._use_ntp:
                        if abs(real_time_diff) > 0.7:
                            TimeUtils._ntp_offset = new_ntp_offset
                            TimeUtils._use_ntp = True
                            Logger.info(f"本机时间偏差较大({real_time_diff:.3f}秒)，已临时启用 NTP 校时模式以确保抢票时间准确")
                        else:
                            Logger.info(f"本机时间偏差较小({real_time_diff:.3f}秒)，继续使用本机时间")
                    else:
                        # 更新现有的NTP偏移
                        old_offset = TimeUtils._ntp_offset
                        TimeUtils._ntp_offset = new_ntp_offset
                        offset_change = new_ntp_offset - old_offset
                        Logger.info(f"已更新 NTP 时间偏移 (偏移变化: {offset_change:.3f}秒)")
                        
                except Exception as e:
                    Logger.warning(f"自动 NTP 校时失败: {e}，将使用当前时间模式")
            
            # 计算开票前延迟设置（支持负数提前抢票）
            delay_ms = self.config.get('pre_delay', {}).get('start_delay_ms', 0)
            target_time = reserve_time + (delay_ms / 1000.0)  # 目标开抢时间
            
            # 等待到达目标开抢时间
            if current_time < target_time:
                remaining_seconds = target_time - current_time
                
                # 开票前5秒停止输出倒计时，并显示待抢状态提示
                if remaining_seconds <= 5:
                    if last_status_time == 0 or current_time > last_status_time + 1:  # 只打印一次或每秒更新一次
                        last_status_time = current_time
                        Logger.info("即将开始抢票，进入待抢状态，不再输出倒计时")
                elif (current_time > last_status_time + 3):
                    last_status_time = current_time
                    reserve_time_str = TimeUtils.timestamp_to_datetime(reserve_time)
                    Logger.info(f'等待开票，距离开票时间 {remaining_seconds:.1f} 秒（{reserve_time_str}）')
                time.sleep(0.1)
                continue
            
            # 到达目标时间，开始抢票
            if delay_ms > 0:
                Logger.info(f"开票时间已到，延迟 {delay_ms} 毫秒后开始抢票...")
            elif delay_ms < 0:
                Logger.info(f"提前 {-delay_ms} 毫秒开始抢票...")
            else:
                Logger.info("开票时间已到，开始抢票...")
            
            # 开始抢票
            return self._start_reservation_loop(ticket_number, activity_id, activity_title)
    

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
                            Logger.warning(f"[线程{thread_id}] [76651] 预约通道拥挤或请求频率过快")
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
            final_result = reservation_worker(1)
        else:
            # 多线程模式
            Logger.info(f"多线程模式开始抢票，线程数：{thread_count}")
            Logger.info("提示：多线程会并发发送请求，可能触发风控，请谨慎使用")
            
            try:
                with ThreadPoolExecutor(max_workers=thread_count) as executor:
                    # 提交所有线程任务
                    futures = [executor.submit(reservation_worker, i+1) for i in range(thread_count)]
                    
                    # 等待第一个完成的线程
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            # 一旦有结果，停止其他线程
                            stop_flag.set()
                            break
                        except Exception as e:
                            Logger.error(f"线程执行异常：{e}")
                            continue
            except KeyboardInterrupt:
                Logger.info("用户中断抢票")
                stop_flag.set()
        
        # 显示最终结果
        if success_flag.is_set():
            Logger.info(f"抢票完成！成功次数：{success_count}")
        else:
            Logger.info(f"抢票结束，未成功。错误次数：{error_count}")
