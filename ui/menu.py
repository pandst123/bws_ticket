"""交互式菜单模块"""
import os
import inquirer
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from utils.logger import Logger
from utils.time import TimeUtils
from utils.config import ConfigManager
from core.reservation import ReservationData


class InteractiveMenu:
    """交互式菜单类"""
    
    @staticmethod
    def clear_screen() -> None:
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def show_menu(title: str, options: list, selected_index: int = 0) -> int:
        """显示菜单并返回选择的索引"""
        try:
            questions = [
                inquirer.List('choice',
                            message=title,
                            choices=options,
                            default=options[selected_index] if 0 <= selected_index < len(options) else options[0])
            ]
            answers = inquirer.prompt(questions)
            
            if answers is None:  # 用户按了 Ctrl+C
                return -1
            
            # 返回选择的索引
            return options.index(answers['choice'])
        except (KeyboardInterrupt, EOFError):
            return -1
    
    @staticmethod
    def show_date_menu(reservation_data: ReservationData) -> Optional[str]:
        """显示日期选择菜单"""
        options = []
        date_mapping = {}
        
        for i, day in enumerate(reservation_data.ticket_days):
            ticket_info = reservation_data.raw_data['user_ticket_info'][day]
            display_text = f"{ticket_info['screen_name']} - {ticket_info['sku_name']}"
            options.append(display_text)
            date_mapping[i] = day
        
        if not options:
            print("\n没有可用的活动日期")
            input("按回车键返回主菜单...")
            return None
        
        selected_index = InteractiveMenu.show_menu("选择查看日期", options)
        if selected_index == -1:
            return None
        
        return date_mapping[selected_index]
    
    @staticmethod
    def show_activity_menu(reservation_data: ReservationData, selected_date: str) -> Optional[int]:
        """显示活动选择菜单"""
        activities = reservation_data.raw_data['reserve_list'][selected_date]
        
        # 加载配置
        config = ConfigManager.load_config()
        hide_ended = config.get('activity_filter', {}).get('hide_ended_reservations', False)
        
        # 过滤活动
        filtered_activities = []
        filtered_count = 0
        
        for activity in activities:
            if hide_ended and activity.get('state') == 3:
                filtered_count += 1
                continue
            filtered_activities.append(activity)
        
        if not filtered_activities:
            if filtered_count > 0:
                print(f"\n{selected_date} 没有可用的活动（已屏蔽 {filtered_count} 个已结束预约的活动）")
            else:
                print(f"\n{selected_date} 没有可用的活动")
            input("按回车键返回主菜单...")
            return None
        
        # 先显示活动信息表格
        print(f"\n{selected_date} 活动信息：")
        console = Console()
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("ID", style="cyan")
        table.add_column("活动名称", style="green")
        table.add_column("预约时间", style="yellow")
        table.add_column("开始时间", style="blue")
        table.add_column("类型", style="red")
        
        for activity in filtered_activities:
            activity_id = activity['reserve_id']
            title = activity['act_title'].replace('\n', '')
            reserve_time_str = TimeUtils.timestamp_to_datetime(activity['reserve_begin_time'])
            start_time_str = TimeUtils.timestamp_to_datetime(activity['act_begin_time'])
            
            # 处理活动提示信息
            if '预约只是签售资格，现场签售需购买up主周边。' in activity['describe_info']:
                warning = "⚠️ 付费内容"
            else:
                warning = "免费活动"
            
            table.add_row(
                str(activity_id),
                title,
                reserve_time_str,
                start_time_str,
                warning
            )
        
        with console.capture() as capture:
            console.print(table)
        print(f"\n{capture.get()}\n")
        
        # 显示过滤信息
        if hide_ended and filtered_count > 0:
            print(f"\n已屏蔽 {filtered_count} 个已结束预约的活动\n")
        
        # 然后显示选择菜单
        options = []
        activity_mapping = {}
        
        for i, activity in enumerate(filtered_activities):
            activity_id = activity['reserve_id']
            title = activity['act_title'].replace('\n', '')
            reserve_time_str = TimeUtils.timestamp_to_datetime(activity['reserve_begin_time'])
            start_time_str = TimeUtils.timestamp_to_datetime(activity['act_begin_time'])
            if '预约只是签售资格，现场签售需购买up主周边。' in activity['describe_info']:
                warning = "[需付费] "
            else:
                warning = ""
            display_text = f"\033[31m{warning}\033[0m{title} | 预约开始 {reserve_time_str} | 活动时间 {start_time_str}"
            options.append(display_text)
            activity_mapping[i] = activity_id
        
        selected_index = InteractiveMenu.show_menu(f"选择要预约的活动", options)
        if selected_index == -1:
            return None
        
        return activity_mapping[selected_index]
    
    @staticmethod
    def show_reservation_mode_menu() -> Optional[str]:
        """显示预约模式选择菜单"""
        options = [
            "准时开抢 - 等待预约时间到达后开始抢票",
            "直接开抢 - 立即开始抢票（忽略预约时间）"
        ]
        
        selected_index = InteractiveMenu.show_menu("选择预约模式", options)
        if selected_index == -1:
            return None
        
        return "scheduled" if selected_index == 0 else "immediate"
