# logging_config.py
# 로깅 관련 함수
import logging
import sys

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler('tagging_tool.log'),
            logging.StreamHandler(sys.stdout)  # 이 줄을 추가합니다.
        ]
    )