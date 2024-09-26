# utils.py
import sys
import os

from typing import List, Dict
from datetime import datetime

def select_account_or_resource(resources: List[Dict]) -> List[Dict]:
    print("\n1. 특정 AWS 계정 선택")
    print("2. 특정 AWS 리소스 타입 선택")
    choice = safe_input("선택하세요 (1 또는 2): ")

    if choice == '1':
        account_id = safe_input("AWS 계정 ID를 입력하세요: ")
        return [r for r in resources if r['Account ID'] == account_id]
    elif choice == '2':
        resource_type = safe_input("리소스 타입을 입력하세요 (예: AWS::EC2::Instance): ")
        return [r for r in resources if r['Resource Type'] == resource_type]
    else:
        print("잘못된 선택입니다.")
        return []
        
def get_csv_filename(default_prefix):
    default_filename = f"{default_prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    
    print(f"기본 파일명 '{default_filename}'을 사용하시겠습니까? (y/n): ", end='', flush=True)
    try:
        use_default = os.read(0, 1024).decode('utf-8').strip().lower() == 'y'
    except UnicodeDecodeError:
        use_default = os.read(0, 1024).decode('iso-8859-1').strip().lower() == 'y'
    
    if use_default:
        return default_filename
    else:
        print("사용할 파일명을 입력하세요: ", end='', flush=True)
        try:
            return os.read(0, 1024).decode('utf-8').strip()
        except UnicodeDecodeError:
            return os.read(0, 1024).decode('iso-8859-1').strip()

def safe_input(prompt):
    print(prompt, end='', flush=True)
    try:
        return os.read(0, 1024).decode('utf-8').strip()
    except UnicodeDecodeError:
        return os.read(0, 1024).decode('iso-8859-1').strip()