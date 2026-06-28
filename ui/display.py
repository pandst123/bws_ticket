"""用户界面显示模块"""
from typing import Optional
from utils.logger import Logger
from utils.cookie import CookieCache
from core.api import BilibiliAPI
from login.qrcode import QRCodeLogin
from ui.menu import InteractiveMenu

VERSION = "1.10.0"


class UserInterface:
    """用户界面类"""
    
    @staticmethod
    def show_welcome_message() -> None:
        """显示欢迎信息"""
        print("""
██████╗ ██╗    ██╗███████╗    ████████╗██╗ ██████╗██╗  ██╗███████╗████████╗
██╔══██╗██║    ██║██╔════╝    ╚══██╔══╝██║██╔════╝██║ ██╔╝██╔════╝╚══██╔══╝
██████╔╝██║ █╗ ██║███████╗       ██║   ██║██║     █████╔╝ █████╗     ██║   
██╔══██╗██║███╗██║╚════██║       ██║   ██║██║     ██╔═██╗ ██╔══╝     ██║   
██████╔╝╚███╔███╔╝███████║       ██║   ██║╚██████╗██║  ██╗███████╗   ██║   
╚═════╝  ╚══╝╚══╝ ╚══════╝       ╚═╝   ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝   ╚═╝   
        """)
        Logger.info(f'BWS Ticket | 当前程序版本：{VERSION}')
        Logger.info(f'本项目在 Starsbon/bws_ticket 开源，欢迎 Star\n')

    
    @staticmethod
    def get_valid_cookie() -> str:
        """获取有效的 Cookie（优先使用缓存）"""
        # 尝试从缓存加载Cookie
        cached_cookie = CookieCache.load_cookie()
        
        if cached_cookie:
            Logger.info("发现 Cookie 缓存，正在验证有效性...")
            try:
                # 验证缓存的Cookie是否有效
                api_client = BilibiliAPI(cached_cookie)
                if api_client.validate_cookie():
                    Logger.info("Cookie 缓存有效，直接使用缓存登录\n")
                    return cached_cookie
                else:
                    Logger.warning("Cookie 缓存已失效，需要重新登录\n")
                    CookieCache.clear_cache()
            except Exception as e:
                Logger.error(f"验证 Cookie 缓存时出错: {e}")
                CookieCache.clear_cache()
        
        # 如果没有缓存或缓存失效，提供登录选项
        while True:
            try:
                login_options = [
                    "扫码登录（推荐）",
                    "手动输入Cookie"
                ]
                
                selected_index = InteractiveMenu.show_menu("请选择登录方式", login_options)
                
                if selected_index == -1:  # ESC退出
                    Logger.info("用户取消登录")
                    exit(0)
                elif selected_index == 0:  # 扫码登录
                    Logger.info("选择扫码登录方式")
                    cookie_string = QRCodeLogin.login_with_qrcode()
                    if cookie_string:
                        # 验证Cookie有效性
                        api_client = BilibiliAPI(cookie_string)
                        if api_client.validate_cookie():
                            Logger.info("Cookie验证成功，正在保存到缓存...")
                            CookieCache.save_cookie(cookie_string)
                            return cookie_string
                        else:
                            Logger.error("获取的Cookie无效")
                            continue
                    else:
                        Logger.warning("扫码登录失败，请重试或选择其他登录方式")
                        continue
                elif selected_index == 1:  # 手动输入Cookie
                    Logger.info("选择手动输入Cookie方式")
                    Logger.info("获取方法：登录bilibili.com后，按F12打开开发者工具，在Network标签页找到任意请求，复制Cookie值")
                    
                    cookie_string = input('请输入Cookie: ').strip()
                    if not cookie_string:
                        Logger.warning("Cookie不能为空，请重新选择登录方式")
                        continue
                    
                    # 验证Cookie
                    api_client = BilibiliAPI(cookie_string)
                    if api_client.validate_cookie():
                        Logger.info("Cookie 验证成功，正在保存到缓存...\n")
                        CookieCache.save_cookie(cookie_string)
                        return cookie_string
                    else:
                        Logger.warning("Cookie 无效，请重新选择登录方式")
                        continue
                        
            except KeyboardInterrupt:
                Logger.info("\n用户取消登录")
                exit(0)
            except Exception as e:
                Logger.error(f"登录过程中发生错误: {e}，请重试")
                continue
