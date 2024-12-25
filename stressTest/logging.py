import logging
from logging.handlers import RotatingFileHandler

def configure_logger(service_id, log_dir="./logs"):
    """
    配置独立日志记录器，为每个服务实例创建一个日志文件。
    :param service_id: 唯一标识服务实例的 ID
    :param log_dir: 日志文件保存的目录，默认为当前目录下的 logs 文件夹
    :return: 配置好的日志记录器
    """
    import os

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(f"service_{service_id}")
    logger.setLevel(logging.INFO)

    # 创建日志文件处理器
    log_filename = os.path.join(log_dir, f"service_{service_id}.log")
    handler = RotatingFileHandler(log_filename, maxBytes=10 * 1024 * 1024, backupCount=3)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # 添加处理器到记录器
    logger.addHandler(handler)

    # 添加控制台日志（可选，便于调试）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
