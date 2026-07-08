"""用户界面显示模块"""
from typing import Optional
from utils.logger import Logger
from utils.cookie import CookieCache
from core.api import BilibiliAPI
from login.qrcode import QRCodeLogin
from ui.menu import InteractiveMenu

VERSION = "2.1.0"


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
        current_uid = CookieCache.get_current_uid()
        
        if cached_cookie:
            Logger.info(f"发现 UID {current_uid} 的 Cookie 缓存，正在验证有效性...")
            try:
                # 验证缓存的Cookie是否有效
                api_client = BilibiliAPI(cached_cookie)
                if api_client.validate_cookie():
                    Logger.info(f"UID {current_uid} 的 Cookie 缓存有效，直接使用缓存登录\n")
                    return cached_cookie
                else:
                    Logger.warning(f"UID {current_uid} 的 Cookie 缓存已失效，需要重新登录\n")
                    if current_uid:
                        CookieCache.remove_cookie(current_uid)
            except Exception as e:
                Logger.error(f"验证 Cookie 缓存时出错: {e}")
                if current_uid:
                    CookieCache.remove_cookie(current_uid)
        
        # 如果没有缓存或缓存失效，提供登录选项
        return UserInterface.login_new_account()
    
    @staticmethod
    def login_new_account() -> str:
        """登录并保存一个新账号"""
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
                    cookie_string = UserInterface._login_with_qrcode()
                    if cookie_string:
                        return cookie_string
                    else:
                        Logger.warning("扫码登录失败，请重试或选择其他登录方式")
                        continue
                elif selected_index == 1:  # 手动输入Cookie
                    cookie_string = UserInterface._login_with_manual_cookie()
                    if cookie_string:
                        return cookie_string
                    else:
                        continue
                        
            except KeyboardInterrupt:
                Logger.info("\n用户取消登录")
                exit(0)
            except Exception as e:
                Logger.error(f"登录过程中发生错误: {e}，请重试")
                continue

    @staticmethod
    def switch_account() -> Optional[str]:
        """显示账号切换菜单，返回切换后的Cookie"""
        while True:
            accounts = CookieCache.list_accounts()
            options = []
            account_uids = []
            
            for account in accounts:
                uid = account['uid']
                current_mark = "（当前）" if account.get('is_current') else ""
                options.append(f"UID: {uid}{current_mark}")
                account_uids.append(uid)
            
            options.extend([
                "添加新账号 - 扫码登录",
                "添加新账号 - 手动输入Cookie"
            ])
            
            if not account_uids:
                return UserInterface.login_new_account()
            
            current_index = 0
            for i, account in enumerate(accounts):
                if account.get('is_current'):
                    current_index = i
                    break
            
            selected_index = InteractiveMenu.show_menu("请选择要切换的账号", options, current_index)
            
            if selected_index == -1:
                Logger.info("已取消切换账号")
                return None
            
            if selected_index < len(account_uids):
                uid = account_uids[selected_index]
                cookie_string = CookieCache.load_cookie_by_uid(uid)
                if not cookie_string:
                    Logger.warning(f"UID {uid} 的 Cookie 不可用，请重新选择")
                    continue
                
                try:
                    api_client = BilibiliAPI(cookie_string)
                    if api_client.validate_cookie():
                        CookieCache.set_current_uid(uid)
                        Logger.info(f"已切换到账号 UID: {uid}\n")
                        return cookie_string
                    Logger.warning(f"UID {uid} 的 Cookie 已失效，已从缓存移除")
                    CookieCache.remove_cookie(uid)
                except Exception as e:
                    Logger.error(f"切换到 UID {uid} 时出错: {e}")
                    CookieCache.remove_cookie(uid)
                continue
            
            if selected_index == len(account_uids):
                cookie_string = UserInterface._login_with_qrcode()
                if cookie_string:
                    return cookie_string
                continue
            
            cookie_string = UserInterface._login_with_manual_cookie()
            if cookie_string:
                return cookie_string
    
    @staticmethod
    def _login_with_qrcode() -> Optional[str]:
        """扫码登录并保存Cookie"""
        Logger.info("选择扫码登录方式")
        cookie_string = QRCodeLogin.login_with_qrcode()
        if not cookie_string:
            return None
        return UserInterface._validate_and_save_cookie(cookie_string)
    
    @staticmethod
    def _login_with_manual_cookie() -> Optional[str]:
        """手动输入Cookie并保存"""
        Logger.info("选择手动输入Cookie方式")
        Logger.info("获取方法：登录bilibili.com后，按F12打开开发者工具，在Network标签页找到任意请求，复制Cookie值")
        
        cookie_string = input('请输入Cookie: ').strip()
        if not cookie_string:
            Logger.warning("Cookie不能为空，请重新选择登录方式")
            return None
        
        return UserInterface._validate_and_save_cookie(cookie_string)
    
    @staticmethod
    def _validate_and_save_cookie(cookie_string: str) -> Optional[str]:
        """验证Cookie有效性并保存到账号缓存"""
        api_client = BilibiliAPI(cookie_string)
        if not api_client.validate_cookie():
            Logger.warning("Cookie 无效，请重新选择登录方式")
            return None
        
        uid = CookieCache.save_cookie(cookie_string)
        if uid:
            Logger.info(f"Cookie 验证成功，已保存账号 UID: {uid}\n")
        else:
            Logger.info("Cookie 验证成功，但保存到缓存失败\n")
        return cookie_string
