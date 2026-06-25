"""BWS Ticket - 哔哩哔哩 BWS 活动预约工具

本工具仅供技术学习，不提供也未进行任何绕过、试图绕过、入侵哔哩哔哩服务器与其服务的任何功能。
"""
import os
import sys
import warnings

# 解决 Windows 终端编码问题
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# 屏蔽 blessed 库的终端能力警告
warnings.filterwarnings('ignore', message='.*terminal capability.*')

import inquirer
from utils.logger import Logger
from utils.time import TimeUtils
from utils.config import ConfigManager
from core.api import BilibiliAPI
from core.reservation import ReservationData, ReservationBot
from ui.menu import InteractiveMenu
from ui.display import UserInterface


def main():
    """主函数"""
    try:
        # 初始化日志系统
        logger = Logger.setup_logger()

        # 显示欢迎信息
        UserInterface.show_welcome_message()
        
        # 获取有效的Cookie（优先使用缓存）
        cookie_string = UserInterface.get_valid_cookie()
        api_client = BilibiliAPI(cookie_string)
        
        # 获取预约信息
        reservation_info = api_client.get_reservation_info()
        if not reservation_info:
            Logger.error('账号信息错误或异常，请检查 网络/账号/Cookies 再试，详细报错见上方。')
            return
        
        # 获取用户已预约的活动信息
        try:
            my_reservations = api_client.get_my_reservations()
        except Exception as e:
            Logger.warning(f"获取用户预约信息失败: {e}，将继续运行但无法过滤已预约活动")
            my_reservations = None
        
        # 初始化数据管理器
        reservation_data = ReservationData(reservation_info, my_reservations)
        
        # 主菜单循环
        while True:
            time_status = "NTP时间" if TimeUtils._use_ntp else "本地时间"
            config = ConfigManager.load_config()
            delay_ms = config.get('pre_delay', {}).get('start_delay_ms', 0)
            loop_delay_ms = config.get('loop_delay', {}).get('loop_delay_ms', 50)
            hide_ended = config.get('activity_filter', {}).get('hide_ended_reservations', False)
            filter_status = "已启用" if hide_ended else "已禁用"
            main_options = [
                "查看所有预约活动",
                "查看指定日期活动",
                "查看我的预约",
                "开始预约抢票",
                f"设置程序校时 (当前: {time_status})",
                f"设置开抢前延迟 (当前: {delay_ms}毫秒)",
                f"设置开抢中延迟 (当前: {loop_delay_ms}毫秒)",
                f"设置屏蔽已结束活动 (当前: {filter_status})",
                "退出程序"
            ]
            
            selected_index = InteractiveMenu.show_menu("BWS Ticket - 主菜单", main_options)
            
            if selected_index == -1 or selected_index == 8:  # ESC或退出
                Logger.info("程序退出")
                break
            elif selected_index == 0:  # 查看所有预约活动
                print("\n" + "="*60)
                print("查看所有预约活动")
                print("="*60)
                reservation_data.display_ticket_info()
                reservation_data.display_activities()
                input("\n按回车键返回主菜单...")
            elif selected_index == 2:  # 查看我的预约
                print("\n" + "="*60)
                print("查看我的预约")
                print("="*60)
                try:
                    my_reservations = api_client.get_my_reservations()
                    if my_reservations:
                        ReservationData.display_my_reservations(my_reservations)
                    else:
                        Logger.error("获取预约信息失败")
                except Exception as e:
                    Logger.error(f"获取预约信息时出错: {e}")
                input("\n按回车键返回主菜单...")
            elif selected_index == 5:  # 设置开抢前延迟
                try:
                    current_delay = config.get('pre_delay', {}).get('start_delay_ms', 0)
                    print(f"\n当前延时设置: {current_delay} 毫秒")
                    print("说明: 本设置影响开票前的动作，正数为延迟（如 100 表示开票后 100ms 开抢），负数为提前（如 -100 表示提前 100ms 开抢）\n")
                    
                    delay_input = input(f"请输入新的延时时间（毫秒）: ").strip()
                    
                    if delay_input == "":
                        Logger.info("未修改延时设置")
                    else:
                        new_delay = int(delay_input)
                        config['pre_delay']['start_delay_ms'] = new_delay
                        ConfigManager.save_config(config)
                        if new_delay >= 0:
                            Logger.info(f"延时设置已更新为: {new_delay} 毫秒（开票后延迟）")
                        else:
                            Logger.info(f"延时设置已更新为: {new_delay} 毫秒（开票前提前 {abs(new_delay)} 毫秒）")
                            
                except ValueError:
                    Logger.warning("请输入有效的数字")
                except (KeyboardInterrupt, EOFError):
                    pass
                
                input("\n按回车键返回主菜单...")
            elif selected_index == 6:  # 设置开抢中延迟
                try:
                    current_delay = config.get('loop_delay', {}).get('loop_delay_ms', 50)
                    print(f"\n当前开抢中延迟设置: {current_delay} 毫秒")
                    print("说明: 本设置影响开抢过程中每次请求之间的延迟时间，设置为0表示不进行延迟，只允许非负数\n")
                    
                    delay_input = input(f"请输入新的开抢中延迟时间（毫秒，>=0）: ").strip()
                    
                    if delay_input == "":
                        Logger.info("未修改开抢中延迟设置")
                    else:
                        new_delay = int(delay_input)
                        if new_delay < 0:
                            Logger.warning("开抢中延迟不能为负数，请输入大于等于0的数值")
                        else:
                            if 'loop_delay' not in config:
                                config['loop_delay'] = {}
                            config['loop_delay']['loop_delay_ms'] = new_delay
                            ConfigManager.save_config(config)
                            if new_delay == 0:
                                Logger.info(f"开抢中延迟已设置为: {new_delay} 毫秒（无延迟）")
                            else:
                                Logger.info(f"开抢中延迟已设置为: {new_delay} 毫秒")
                            
                except ValueError:
                    Logger.warning("请输入有效的数字")
                except (KeyboardInterrupt, EOFError):
                    pass
                
                input("\n按回车键返回主菜单...")
            elif selected_index == 7:  # 设置屏蔽已结束活动
                try:
                    current_hide = config.get('activity_filter', {}).get('hide_ended_reservations', False)
                    status_text = "已启用" if current_hide else "已禁用"
                    print(f"\n当前设置: 屏蔽已结束预约活动 - {status_text}")
                    print("说明: 启用后将为您隐藏不可预约的活动（含已预约成功的活动）")
                    
                    filter_options = [
                        "禁用屏蔽 - 显示所有活动",
                        "启用屏蔽 - 隐藏已结束预约、已预约的活动"
                    ]
                    
                    current_option = 1 if current_hide else 0
                    filter_selected = InteractiveMenu.show_menu("活动过滤设置", filter_options, current_option)
                    
                    if filter_selected == -1:
                        pass  # 用户取消
                    elif filter_selected == 0:
                        config['activity_filter']['hide_ended_reservations'] = False
                        ConfigManager.save_config(config)
                        Logger.info("已禁用活动过滤，将显示所有活动")
                    elif filter_selected == 1:
                        config['activity_filter']['hide_ended_reservations'] = True
                        ConfigManager.save_config(config)
                        Logger.info("已启用活动过滤，将屏蔽已结束预约和已预约的活动")
                        
                except (KeyboardInterrupt, EOFError):
                    pass
                
                input("\n按回车键返回主菜单...")

            elif selected_index == 1:  # 查看指定日期活动
                selected_date = InteractiveMenu.show_date_menu(reservation_data)
                if selected_date:
                    print("\n" + "="*60)
                    print(f"查看 {selected_date} 活动信息")
                    print("="*60)
                    reservation_data.display_activities_for_date(selected_date)
                    input("\n按回车键返回主菜单...")
            elif selected_index == 3:  # 开始预约抢票
                # 选择日期
                selected_date = InteractiveMenu.show_date_menu(reservation_data)
                if not selected_date:
                    continue
                
                # 选择活动
                selected_activity_id = InteractiveMenu.show_activity_menu(reservation_data, selected_date)
                if not selected_activity_id:
                    continue
                
                # 选择预约模式
                reservation_mode = InteractiveMenu.show_reservation_mode_menu()
                if not reservation_mode:
                    continue
                
                # 显示预约确认信息
                activity_title = reservation_data.activity_mapping[selected_activity_id][0]
                mode_text = "准时开抢" if reservation_mode == "scheduled" else "直接开抢"
                
                # 使用 inquirer 进行确认
                try:
                    confirm_question = [
                        inquirer.Confirm('confirm',
                                       message="确认开始预约？",
                                       default=False)
                    ]
                    confirm_answer = inquirer.prompt(confirm_question)
                    
                    if not confirm_answer or not confirm_answer['confirm']:
                        continue
                except (KeyboardInterrupt, EOFError):
                    continue
                
                # 开始预约
                print("\n" + "="*60)
                Logger.info(f"当前项目：{activity_title}")
                Logger.info(f"当前模式：{mode_text}")
                Logger.info("按 Ctrl+C 可以中断抢票\n")
                
                bot = ReservationBot(api_client, reservation_data)
                bot.wait_and_reserve(selected_activity_id, reservation_mode)
                
                input("\n预约结束，按回车键返回主菜单...")
            elif selected_index == 4:  # 设置程序校时
                time_options = [
                    "使用本地时间",
                    "使用 Aliyun NTP 时间"
                ]
                
                current_mode = 1 if TimeUtils._use_ntp else 0
                time_selected = InteractiveMenu.show_menu("选择时间模式", time_options, current_mode)
                
                if time_selected == -1:
                    continue
                elif time_selected == 0:
                    TimeUtils.set_ntp_mode(False)
                    Logger.info("已切换到本地时间模式")
                elif time_selected == 1:
                    Logger.info("正在进行 NTP 校时...")
                    TimeUtils.set_ntp_mode(True)
                
                input("\n按回车键返回主菜单...")
        
    except ValueError as e:
        Logger.error(f"配置错误: {e}")
    except KeyboardInterrupt:
        Logger.info("\n用户取消操作")
    except Exception as e:
        Logger.error(f"程序运行出错: {e}")
        input("按回车键退出...")


if __name__ == '__main__':
    main()
