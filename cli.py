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
from utils.cookie import CookieCache
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

        startup_config = ConfigManager.load_config()
        if startup_config.get('time_calibration', {}).get('mode') == 'ntp':
            Logger.info("配置为 NTP 时间模式，正在进行启动校时...")
            TimeUtils.set_ntp_mode(True)

        def format_time_status():
            """格式化主菜单校时状态。"""
            status = TimeUtils.get_status()
            if status["use_ntp"]:
                server = status.get("last_server") or "未知服务器"
                offset = status.get("offset_seconds") or 0
                return f"NTP时间 {offset:+.3f}秒 ({server})"
            return "本地时间"

        def display_time_status():
            """显示当前校时状态。"""
            status = TimeUtils.get_status()
            mode_text = "NTP时间" if status["use_ntp"] else "本地时间"
            print(f"\n当前时间模式: {mode_text}")
            print(f"当前程序内偏移: {status.get('offset_seconds', 0):+.3f} 秒")

            calibrated_at = status.get("last_calibrated_at")
            if calibrated_at:
                calibrated_at_text = TimeUtils.timestamp_to_datetime(calibrated_at)
                print(f"最近校准时间: {calibrated_at_text}")
            if status.get("last_server"):
                print(f"最近校准服务器: {status['last_server']}")
            if status.get("last_round_trip_ms") is not None:
                print(f"最近校准往返耗时: {status['last_round_trip_ms']:.1f} ms")
            if status.get("last_sample_count") is not None:
                print(f"最近校准采样数: {status['last_sample_count']} 次")
            if status.get("last_offset_spread_ms") is not None:
                print(f"最近校准偏移波动: {status['last_offset_spread_ms']:.1f} ms")
            if status.get("last_stability_warning"):
                print(f"最近校准稳定性提示: {status['last_stability_warning']}")
            if status.get("last_error"):
                print(f"最近校准错误: {status['last_error']}")

        def load_account_context(cookie_value):
            """根据Cookie初始化账号上下文（含活动与商品数据）"""
            new_api_client = BilibiliAPI(cookie_value)

            reservation_info = new_api_client.get_reservation_info()
            if not reservation_info:
                Logger.error('账号信息错误或异常，请检查 网络/账号/Cookies 再试，详细报错见上方。')
                return None

            try:
                my_reservations = new_api_client.get_my_reservations()
            except Exception as e:
                Logger.warning(f"获取用户预约信息失败: {e}，将继续运行但无法过滤已预约活动")
                my_reservations = None

            new_reservation_data = ReservationData(reservation_info, my_reservations)

            # 初始化商品数据
            new_goods_reservation_data = None
            try:
                goods_data = new_api_client.get_goods_info()
                if goods_data:
                    new_goods_reservation_data = ReservationData(goods_data, my_reservations)
            except Exception as e:
                Logger.warning(f"获取商品信息失败: {e}，商品抢购功能将不可用")

            return new_api_client, new_reservation_data, new_goods_reservation_data

        # 获取有效的Cookie（优先使用缓存）
        cookie_string = UserInterface.get_valid_cookie()
        account_context = load_account_context(cookie_string)
        if not account_context:
            return
        api_client, reservation_data, goods_reservation_data = account_context

        # 主菜单循环
        while True:
            current_uid = CookieCache.get_uid_from_cookie(cookie_string) or CookieCache.get_current_uid() or "未知"
            time_status = format_time_status()
            config = ConfigManager.load_config()
            delay_ms = config.get('pre_delay', {}).get('start_delay_ms', 0)
            loop_delay_ms = config.get('loop_delay', {}).get('loop_delay_ms', 50)
            hide_ended = config.get('activity_filter', {}).get('hide_ended_reservations', False)
            filter_status = "已启用" if hide_ended else "已禁用"
            thread_count = config.get('thread_count', 1)
            main_options = [
                "开抢活动参与资格",
                "开抢商品购买资格" if goods_reservation_data else "开抢商品购买资格 (无商品数据)",
                "查看所有预约活动",
                "查看指定日期活动",
                "查看我的票种",
                "查看我的预约",
                f"设置程序校时 (当前: {time_status})",
                f"设置开抢前延迟 (当前: {delay_ms}毫秒)",
                f"设置开抢中延迟 (当前: {loop_delay_ms}毫秒)",
                f"设置并发线程数 (当前: {thread_count}线程)",
                f"设置屏蔽已结束活动 (当前: {filter_status})",
                f"切换账号 (当前: UID {current_uid})",
                "退出程序"
            ]

            selected_index = InteractiveMenu.show_menu("BWS Ticket - 主菜单", main_options)

            if selected_index == -1 or selected_index == 12:  # ESC或退出
                Logger.info("程序退出")
                break
            elif selected_index == 0:  # 开抢活动参与资格
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

                # 使用 input 进行确认（支持直接回车）
                try:
                    print(f"\n活动：{activity_title}")
                    print(f"模式：{mode_text}")
                    confirm_input = input("确认开始预约？(Y/n): ").strip().lower()
                    Logger.enable_uid(current_uid)

                    if confirm_input == 'n':
                        Logger.info("已取消预约")
                        continue
                except (KeyboardInterrupt, EOFError):
                    continue

                # 开始预约
                print("\n" + "="*60)
                Logger.info(f"当前项目：{activity_title}")
                Logger.info(f"当前模式：{mode_text}")
                Logger.info("按 Ctrl+C 可以中断抢票\n")

                bot = ReservationBot(api_client, reservation_data)
                result = bot.wait_and_reserve(selected_activity_id, selected_date, reservation_mode)

                # 检查是否是 412 错误
                if result and result.get("code") == 412:
                    input("\n按任意键返回主菜单...")
                else:
                    input("\n预约结束，按回车键返回主菜单...")
            elif selected_index == 1:  # 开抢商品购买资格
                if not goods_reservation_data:
                    Logger.error("商品数据未加载，无法进行商品抢票")
                    input("\n按回车键返回主菜单...")
                    continue

                # 选择日期
                selected_date = InteractiveMenu.show_date_menu(goods_reservation_data)
                if not selected_date:
                    continue

                # 选择商品
                selected_activity_id = InteractiveMenu.show_activity_menu(goods_reservation_data, selected_date)
                if not selected_activity_id:
                    continue

                # 选择预约模式
                reservation_mode = InteractiveMenu.show_reservation_mode_menu()
                if not reservation_mode:
                    continue

                # 显示预约确认信息
                activity_title = goods_reservation_data.activity_mapping[selected_activity_id][0]
                mode_text = "准时开抢" if reservation_mode == "scheduled" else "直接开抢"

                # 使用 input 进行确认（支持直接回车）
                try:
                    print(f"\n商品：{activity_title}")
                    print(f"模式：{mode_text}")
                    confirm_input = input("确认开始商品抢票？(Y/n): ").strip().lower()
                    Logger.enable_uid(current_uid)

                    if confirm_input == 'n':
                        Logger.info("已取消商品抢票")
                        continue
                except (KeyboardInterrupt, EOFError):
                    continue

                # 开始商品抢票
                print("\n" + "="*60)
                Logger.info(f"当前商品：{activity_title}")
                Logger.info(f"当前模式：{mode_text}")
                Logger.info("按 Ctrl+C 可以中断抢票\n")

                bot = ReservationBot(api_client, goods_reservation_data)
                result = bot.wait_and_reserve(selected_activity_id, selected_date, reservation_mode)

                # 检查是否是 412 错误
                if result and result.get("code") == 412:
                    input("\n按任意键返回主菜单...")
                else:
                    input("\n商品抢票结束，按回车键返回主菜单...")
            elif selected_index == 2:  # 查看所有预约活动
                print("\n" + "="*60)
                print("查看所有预约活动")
                print("="*60)
                reservation_data.display_ticket_info()
                reservation_data.display_activities()
                input("\n按回车键返回主菜单...")
            elif selected_index == 3:  # 查看指定日期活动
                selected_date = InteractiveMenu.show_date_menu(reservation_data)
                if selected_date:
                    print("\n" + "="*60)
                    print(f"查看 {selected_date} 活动信息")
                    print("="*60)
                    reservation_data.display_activities_for_date(selected_date)
                    input("\n按回车键返回主菜单...")
            elif selected_index == 4:  # 查看我的票种
                print("\n" + "="*60)
                print("查看我的票种")
                print("="*60)
                reservation_data.display_ticket_info()
                input("\n按回车键返回主菜单...")
            elif selected_index == 5:  # 查看我的预约
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
            elif selected_index == 6:  # 设置程序校时
                time_options = [
                    "使用本地时间",
                    "启用 NTP 时间并立即校准",
                    "立即校准一次并查看本机偏差（不切换模式）",
                    "查看当前校时状态"
                ]

                current_mode = 1 if TimeUtils._use_ntp else 0
                time_selected = InteractiveMenu.show_menu("选择时间模式", time_options, current_mode)

                if time_selected == -1:
                    continue
                elif time_selected == 0:
                    TimeUtils.set_ntp_mode(False)
                    if 'time_calibration' not in config:
                        config['time_calibration'] = {}
                    config['time_calibration']['mode'] = 'local'
                    ConfigManager.save_config(config)
                    Logger.info("已切换到本地时间模式")
                elif time_selected == 1:
                    Logger.info("正在进行 NTP 校时...")
                    result = TimeUtils.set_ntp_mode(True)
                    if result and result.success:
                        if 'time_calibration' not in config:
                            config['time_calibration'] = {}
                        config['time_calibration']['mode'] = 'ntp'
                        ConfigManager.save_config(config)
                    else:
                        Logger.warning("NTP 校时未成功，当前仍使用本地时间")
                elif time_selected == 2:
                    Logger.info("正在进行 NTP 偏差检测（不会切换当前时间模式）...")
                    result = TimeUtils.calibrate(apply_offset=False)
                    if result.success:
                        Logger.info(
                            f"偏差检测完成，服务器: {result.server}，"
                            f"本机时间与 NTP 差值: {result.offset_seconds:+.3f}秒，"
                            f"往返耗时: {result.round_trip_ms:.1f}ms，"
                            f"采样: {result.sample_count}次，"
                            f"偏移波动: {result.offset_spread_ms:.1f}ms"
                        )
                        if result.stability_warning:
                            Logger.warning(f"校准稳定性提示: {result.stability_warning}")
                    else:
                        Logger.warning(f"偏差检测失败: {result.error}")
                elif time_selected == 3:
                    display_time_status()

                input("\n按回车键返回主菜单...")
            elif selected_index == 7:  # 设置开抢前延迟
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
            elif selected_index == 8:  # 设置开抢中延迟
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
            elif selected_index == 9:  # 设置并发线程数
                try:
                    current_threads = config.get('thread_count', 1)
                    print(f"\n当前并发线程数设置: {current_threads} 线程")
                    print("多线程会并发发送预约请求，可能提高成功率，但也可能触发风控")
                    print("不建议修改本参数，速度过快可能导致您被 412 临时限流")

                    thread_input = input(f"请输入新的并发线程数（1-10）: ").strip()

                    if thread_input == "":
                        Logger.info("未修改线程数设置")
                    else:
                        new_threads = int(thread_input)
                        if new_threads < 1:
                            Logger.warning("线程数不能小于1")
                        elif new_threads > 10:
                            Logger.warning("线程数不建议超过10，可能触发风控")
                            # 仍然允许设置，但给出警告
                            config['thread_count'] = new_threads
                            ConfigManager.save_config(config)
                            Logger.info(f"线程数已设置为: {new_threads}（请注意风控风险）")
                        else:
                            config['thread_count'] = new_threads
                            ConfigManager.save_config(config)
                            if new_threads == 1:
                                Logger.info(f"线程数已设置为: {new_threads}（单线程模式）")
                            else:
                                Logger.info(f"线程数已设置为: {new_threads}（多线程模式）")

                except ValueError:
                    Logger.warning("请输入有效的数字")
                except (KeyboardInterrupt, EOFError):
                    pass

                input("\n按回车键返回主菜单...")
            elif selected_index == 10:  # 设置屏蔽已结束活动
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
            elif selected_index == 11:  # 切换账号
                old_cookie_string = cookie_string
                old_uid = CookieCache.get_current_uid()
                new_cookie_string = UserInterface.switch_account()
                if new_cookie_string:
                    account_context = load_account_context(new_cookie_string)
                    if account_context:
                        cookie_string = new_cookie_string
                        api_client, reservation_data, goods_reservation_data = account_context
                        new_uid = CookieCache.get_uid_from_cookie(cookie_string) or CookieCache.get_current_uid() or "未知"
                        Logger.info(f"账号数据已刷新，当前账号 UID: {new_uid}")
                    else:
                        cookie_string = old_cookie_string
                        if old_uid:
                            CookieCache.set_current_uid(old_uid)
                        Logger.error("切换账号失败，已保留当前账号")

                input("\n按回车键返回主菜单...")

    except ValueError as e:
        Logger.error(f"配置错误: {e}")
        input("按回车键退出...")
    except Exception as e:
        Logger.error(f"程序运行出错: {e}")
        input("按回车键退出...")


if __name__ == '__main__':
    main()
