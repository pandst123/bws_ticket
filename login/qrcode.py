"""二维码登录模块"""
import time
import requests
import urllib.parse
import hashlib
import threading
import qrcode_terminal
import qrcode
from typing import Optional
from utils.logger import Logger


class QRCodeLogin:
    """二维码登录功能类"""
    
    @staticmethod
    def tvsign(params: dict, appkey: str = '4409e2ce8ffd12b8', appsec: str = '59b43e04ad6965f34319062b478f83dd') -> dict:
        """为请求参数进行 api 签名"""
        params.update({'appkey': appkey})
        params = dict(sorted(params.items()))  # 重排序参数 key
        query = urllib.parse.urlencode(params)  # 序列化参数
        sign = hashlib.md5((query + appsec).encode()).hexdigest()  # 计算 api 签名
        params.update({'sign': sign})
        return params
    
    @staticmethod
    def show_qr_popup(qr_url: str) -> threading.Thread:
        """直接打开二维码图片"""
        def show_image():
            try:
                # 生成二维码图片
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_url)
                qr.make(fit=True)
                
                # 创建二维码图片
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                # 直接显示图片（会使用系统默认图片查看器打开）
                qr_img.show()
                    
            except Exception as e:
                Logger.error(f"显示二维码图片失败: {e}")
        
        # 在新线程中显示图片，避免阻塞主程序
        show_thread = threading.Thread(target=show_image, daemon=True)
        show_thread.start()
        return show_thread
    
    @staticmethod
    def login_with_qrcode() -> Optional[str]:
        """通过二维码登录获取Cookie"""
        try:
            Logger.info("正在获取二维码...")
            
            # 获取二维码
            login_info = requests.post(
                'https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code',
                params=QRCodeLogin.tvsign({
                    'local_id': '0',
                    'ts': int(time.time())
                }),
                headers={
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                },
                timeout=10
            ).json()
            
            if login_info.get('code') != 0:
                Logger.error(f"获取二维码失败: {login_info.get('message', '未知错误')}")
                return None
            
            # 生成二维码
            print("\n请使用哔哩哔哩手机客户端扫描以下二维码登录：")
            print("=" * 60)
            qrcode_terminal.draw(login_info['data']['url'])
            print("=" * 60)
            
            # 同时打开二维码图片
            Logger.info("正在打开二维码图片...")
            QRCodeLogin.show_qr_popup(login_info['data']['url'])
            
            Logger.info("等待扫码登录...")
            
            # 轮询登录状态
            auth_code = login_info['data']['auth_code']
            while True:
                try:
                    poll_info = requests.post(
                        'https://passport.bilibili.com/x/passport-tv-login/qrcode/poll',
                        params=QRCodeLogin.tvsign({
                            'auth_code': auth_code,
                            'local_id': '0',
                            'ts': int(time.time())
                        }),
                        headers={
                            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                        },
                        timeout=10
                    ).json()
                    
                    if poll_info['code'] == 0:
                        # 登录成功
                        login_data = poll_info['data']
                        Logger.info(f"登录成功！有效期至 {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + int(login_data['expires_in'])))}")
                        
                        # 提取Cookie信息
                        cookie_info = login_data.get('cookie_info', {})
                        cookies = cookie_info.get('cookies', [])
                        
                        # 构建Cookie字符串
                        cookie_parts = []
                        for cookie in cookies:
                            cookie_parts.append(f"{cookie['name']}={cookie['value']}")
                        
                        cookie_string = '; '.join(cookie_parts)
                        
                        if not cookie_string:
                            Logger.error("获取Cookie失败：登录响应中没有Cookie信息")
                            return None
                        
                        return cookie_string
                        
                    elif poll_info['code'] == -3:
                        Logger.error('API校验密匙错误')
                        return None
                    elif poll_info['code'] == -400:
                        Logger.error('请求错误')
                        return None
                    elif poll_info['code'] == 86038:
                        Logger.error('二维码已失效，请重新获取')
                        return None
                    elif poll_info['code'] == 86039:
                        # 二维码未确认，继续等待
                        time.sleep(2)
                        continue
                    else:
                        Logger.error(f'未知错误: {poll_info.get("message", "未知错误")}')
                        return None
                        
                except requests.RequestException as e:
                    Logger.error(f"网络请求失败: {e}")
                    time.sleep(2)
                    continue
                except KeyboardInterrupt:
                    Logger.info("\n用户取消扫码登录")
                    return None
                    
        except Exception as e:
            Logger.error(f"扫码登录过程中发生错误: {e}")
            return None
