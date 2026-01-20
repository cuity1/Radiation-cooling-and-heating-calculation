"""
时间验证模块 - 支持腾讯云和阿里云时间服务
用于许可证过期检查的时间同步验证
"""

import socket
import time
import struct
from datetime import datetime, timezone
from typing import Tuple, Optional


class TimeVerificationError(Exception):
    """时间验证异常"""
    pass


class TencentCloudTimeVerifier:
    """腾讯云时间验证器 - 使用 NTP 协议"""
    
    # 腾讯云 NTP 服务器
    SERVERS = [
        'ntp.tencent.com',
        'ntp1.tencent.com',
        'ntp2.tencent.com',
        'ntp3.tencent.com',
        'ntp4.tencent.com',
        'ntp5.tencent.com',
    ]
    
    NTP_PORT = 123
    TIMEOUT = 5  # 秒
    
    @staticmethod
    def _ntp_request(server: str, timeout: int = TIMEOUT) -> Optional[float]:
        """
        发送 NTP 请求获取服务器时间戳
        
        Args:
            server: NTP 服务器地址
            timeout: 超时时间（秒）
        
        Returns:
            Unix 时间戳（秒），或 None 如果失败
        """
        try:
            # NTP 请求包（48 字节）
            ntp_query = b'\x1b' + b'\x00' * 47
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            sock.sendto(ntp_query, (server, TencentCloudTimeVerifier.NTP_PORT))
            response, _ = sock.recvfrom(1024)
            sock.close()
            
            if len(response) < 48:
                return None
            
            # 解析 NTP 响应（字节 40-43 是传输时间戳）
            ntp_time = struct.unpack('!I', response[40:44])[0]
            # NTP 时间戳是从 1900-01-01 开始，需要转换为 Unix 时间戳（从 1970-01-01 开始）
            unix_timestamp = ntp_time - 2208988800
            
            return float(unix_timestamp)
        except Exception as e:
            return None
    
    @classmethod
    def get_current_time(cls) -> Tuple[bool, Optional[datetime], str]:
        """
        从腾讯云 NTP 服务器获取当前时间
        
        Returns:
            (成功标志, datetime 对象或 None, 消息)
        """
        for server in cls.SERVERS:
            try:
                timestamp = cls._ntp_request(server, cls.TIMEOUT)
                if timestamp is not None:
                    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    return True, dt, f"从腾讯云 NTP 服务器 {server} 获取时间成功"
            except Exception:
                continue
        
        return False, None, "腾讯云时间验证失败：无法连接任何服务器"


class AlibabaCloudTimeVerifier:
    """阿里云时间验证器 - 使用 HTTP API"""
    
    # 阿里云时间服务 API
    ENDPOINTS = [
        'http://ntp.aliyun.com',
        'http://time.aliyun.com',
    ]
    
    TIMEOUT = 5  # 秒
    
    @staticmethod
    def _http_request(endpoint: str, timeout: int = TIMEOUT) -> Optional[float]:
        """
        通过 HTTP 请求获取阿里云时间
        
        Args:
            endpoint: 阿里云时间服务端点
            timeout: 超时时间（秒）
        
        Returns:
            Unix 时间戳（秒），或 None 如果失败
        """
        try:
            import urllib.request
            import urllib.error
            
            req = urllib.request.Request(endpoint)
            req.add_header('User-Agent', 'TimeVerification/1.0')
            
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # 阿里云 NTP 服务返回的是纯数字时间戳（毫秒）
                content = response.read().decode('utf-8').strip()
                
                # 尝试解析为毫秒时间戳
                try:
                    timestamp_ms = int(content)
                    # 转换为秒
                    return float(timestamp_ms) / 1000.0
                except ValueError:
                    # 如果不是纯数字，尝试从响应头获取
                    date_header = response.headers.get('Date')
                    if date_header:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(date_header)
                        return dt.timestamp()
                    return None
        except Exception:
            return None
    
    @classmethod
    def get_current_time(cls) -> Tuple[bool, Optional[datetime], str]:
        """
        从阿里云时间服务获取当前时间
        
        Returns:
            (成功标志, datetime 对象或 None, 消息)
        """
        for endpoint in cls.ENDPOINTS:
            try:
                timestamp = cls._http_request(endpoint, cls.TIMEOUT)
                if timestamp is not None:
                    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    return True, dt, f"从阿里云时间服务 {endpoint} 获取时间成功"
            except Exception:
                continue
        
        return False, None, "阿里云时间验证失败：无法连接任何服务器"


class DualCloudTimeVerifier:
    """双云时间验证器 - 优先使用腾讯云，备用阿里云"""
    
    @staticmethod
    def get_verified_time() -> Tuple[bool, Optional[datetime], str]:
        """
        获取经过验证的当前时间
        
        验证策略：
        1. 优先尝试腾讯云 NTP
        2. 腾讯云失败则尝试阿里云 HTTP API
        3. 两者都失败则返回失败
        
        Returns:
            (成功标志, datetime 对象或 None, 详细消息)
        """
        # 尝试腾讯云
        success, dt, msg = TencentCloudTimeVerifier.get_current_time()
        if success and dt is not None:
            return True, dt, f"[腾讯云] {msg}"
        
        tencent_msg = msg
        
        # 腾讯云失败，尝试阿里云
        success, dt, msg = AlibabaCloudTimeVerifier.get_current_time()
        if success and dt is not None:
            return True, dt, f"[阿里云] {msg}"
        
        alibaba_msg = msg
        
        # 两者都失败
        error_msg = f"时间验证失败：\n  - {tencent_msg}\n  - {alibaba_msg}"
        return False, None, error_msg


def verify_license_with_cloud_time(expiration_date: datetime) -> Tuple[bool, str]:
    """
    使用云服务时间验证许可证是否过期
    
    Args:
        expiration_date: 许可证过期日期（UTC）
    
    Returns:
        (是否有效, 消息)
    
    Raises:
        TimeVerificationError: 如果无法获取云时间
    """
    success, current_time, msg = DualCloudTimeVerifier.get_verified_time()
    
    if not success or current_time is None:
        # 两个云服务都连不上，无法进入程序
        raise TimeVerificationError(
            f"无法进行许可证验证：{msg}\n"
            f"请检查网络连接，确保能访问腾讯云或阿里云时间服务。"
        )
    
    # 成功获取云时间，进行过期检查
    if current_time >= expiration_date:
        return False, f"许可证已过期（云时间：{current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}）"
    
    days_left = (expiration_date - current_time).days
    return True, f"许可证有效（有效至 {expiration_date.strftime('%Y-%m-%d')}，剩余约 {days_left} 天，云时间：{current_time.strftime('%Y-%m-%d %H:%M:%S UTC')}）"

