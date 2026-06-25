"""日志管理模块"""
import logging
import datetime
from logging.handlers import RotatingFileHandler
from rich.console import Console
from rich.text import Text

console = Console()


class RichHandler(logging.Handler):
    """Rich 彩色日志处理器"""
    
    COLORS = {
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'DEBUG': 'blue',
    }
    
    def __init__(self):
        super().__init__()
    
    def emit(self, record):
        try:
            # 创建带颜色的文本
            text = Text()
            
            # 时间戳（灰色）
            timestamp = datetime.datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
            text.append(f"{timestamp}.{int(record.msecs):03d}", style="dim")
            text.append(" - ", style="dim")
            
            # 级别标签（带颜色背景）
            level = record.levelname
            color = self.COLORS.get(level, 'white')
            text.append(f" {level} ", style=f"bold {color} on black")
            text.append(" ", style="dim")
            
            # 消息内容
            text.append(record.getMessage(), style=color)
            
            console.print(text)
        except Exception:
            self.handleError(record)


class Logger:
    """日志管理器"""
    
    _logger = None
    
    @classmethod
    def setup_logger(cls) -> logging.Logger:
        """设置日志记录器"""
        if cls._logger is None:
            cls._logger = logging.getLogger('bws_cli')
            cls._logger.setLevel(logging.INFO)
            
            # 避免重复添加handler
            if not cls._logger.handlers:
                # 创建文件handler（带轮转）
                file_handler = RotatingFileHandler(
                    'bws_reservation.log', 
                    maxBytes=10*1024*1024,  # 10MB
                    backupCount=5,
                    encoding='utf-8'
                )
                file_handler.setLevel(logging.INFO)
                
                # 创建Rich彩色控制台handler
                console_handler = RichHandler()
                console_handler.setLevel(logging.INFO)
                
                # 创建文件格式器
                file_formatter = logging.Formatter(
                    '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                
                file_handler.setFormatter(file_formatter)
                
                # 添加handler到logger
                cls._logger.addHandler(file_handler)
                cls._logger.addHandler(console_handler)
        
        return cls._logger
    
    @classmethod
    def info(cls, message: str) -> None:
        """输出信息级别日志"""
        if cls._logger is None:
            cls.setup_logger()
        cls._logger.info(message)
    
    @classmethod
    def error(cls, message: str) -> None:
        """输出错误级别日志"""
        if cls._logger is None:
            cls.setup_logger()
        cls._logger.error(message)
    
    @classmethod
    def warning(cls, message: str) -> None:
        """输出警告级别日志"""
        if cls._logger is None:
            cls.setup_logger()
        cls._logger.warning(message)
    
    @classmethod
    def success(cls, message: str) -> None:
        """输出成功信息（绿色加粗）"""
        if cls._logger is None:
            cls.setup_logger()
        # 使用自定义的控制台输出
        text = Text()
        text.append(" ✓ ", style="bold green on black")
        text.append(" ", style="dim")
        text.append(message, style="bold green")
        console.print(text)
        # 同时写入文件
        cls.log_to_file_only(f"SUCCESS - {message}")
    
    @classmethod
    def log_to_file_only(cls, message: str, level: str = 'INFO') -> None:
        """仅写入文件的日志，不在控制台显示"""
        if cls._logger is None:
            cls.setup_logger()
        
        # 创建一个临时的只有文件handler的logger
        file_only_logger = logging.getLogger('bws_cli_file_only')
        file_only_logger.setLevel(logging.INFO)
        
        # 避免重复添加handler
        if not file_only_logger.handlers:
            file_handler = RotatingFileHandler(
                'bws_reservation.log', 
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.INFO)
            file_formatter = logging.Formatter(
                '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', 
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            file_only_logger.addHandler(file_handler)
        
        if level.upper() == 'ERROR':
            file_only_logger.error(message)
        else:
            file_only_logger.info(message)
