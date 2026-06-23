"""日志管理模块"""
import logging
from logging.handlers import RotatingFileHandler


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
                
                # 创建控制台handler
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.INFO)
                
                # 创建格式器（精确到毫秒）
                file_formatter = logging.Formatter(
                    '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                console_formatter = logging.Formatter(
                    '%(asctime)s.%(msecs)03d - %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                
                file_handler.setFormatter(file_formatter)
                console_handler.setFormatter(console_formatter)
                
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
