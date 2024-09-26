# -*- coding: utf-8 -*-
# 메인 함수. 리소스 정보를 검색, 태깅, csv export 등을 정의
import boto3
import sys
import io
import os

from datetime import datetime
from collections import defaultdict
from aws_config_explorer import get_all_resources, get_supported_resource_types, get_all_accounts, get_all_ou_ids
from tagging_operations import add_tags, remove_tags, add_tags_from_csv, remove_tags_from_csv
from csv_operations import save_to_csv, save_tagged_resources_to_csv, read_csv_for_tagging, update_csv_with_tagged_resources
from utils import select_account_or_resource, get_csv_filename, safe_input
import logging
from logging_config import setup_logging
from config import SSO_PROFILE, REGIONS, ASSUME_ROLE_NAME, MAX_CONCURRENT_ACCOUNTS, MAX_CONCURRENT_REGIONS

sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

def main():
    sys.stdin = sys.__stdin__
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    setup_logging()

    session = boto3.Session(profile_name=SSO_PROFILE)

    search_option = safe_input("""리소스 검색 옵션 선택:
1. AWS Account ID 입력
2. AWS OU ID 입력
3. 전체 대상으로 검색
4. CSV로 태깅 작업 수행
선택: """).strip()

    if search_option in ['1', '2', '3']:
        org_client = session.client('organizations')
        
        if search_option == '1':
            all_accounts = get_all_accounts(org_client)
            print("사용 가능한 AWS 계정:")
            for i, (account_id, account_name) in enumerate(all_accounts, 1):
                print(f"{i}. {account_id} - {account_name}")
            account_choice = safe_input("선택할 계정 번호를 입력하세요 (쉼표로 구분하여 여러 개 선택 가능, 전체 선택은 'all'): ")
            if account_choice.lower() == 'all':
                account_ids = [account[0] for account in all_accounts]
            else:
                account_ids = [all_accounts[int(i) - 1][0] for i in account_choice.split(',')]
            ou_ids = None
            logging.info(f"Selected accounts: {account_ids}")

        elif search_option == '2':
            all_ous = get_all_ou_ids(org_client)
            print("사용 가능한 AWS OU:")
            for i, (ou_id, ou_name) in enumerate(all_ous, 1):
                print(f"{i}. {ou_id} - {ou_name}")
            ou_choice = safe_input("선택할 OU 번호를 입력하세요 (쉼표로 구분하여 여러 개 선택 가능, 전체 선택은 'all'): ")
            if ou_choice.lower() == 'all':
                ou_ids = [ou[0] for ou in all_ous]
            else:
                ou_ids = [all_ous[int(i) - 1][0] for i in ou_choice.split(',')]
            account_ids = None
            logging.info(f"Selected OUs: {ou_ids}")

        else:  # search_option == '3'
            ou_ids = get_all_ou_ids(org_client)
            account_ids = get_all_accounts(org_client)

        try:
            resources, accounts_with_many_resources = get_all_resources(
                session=session, 
                regions=REGIONS, 
                assume_role_name=ASSUME_ROLE_NAME, 
                max_concurrent_accounts=MAX_CONCURRENT_ACCOUNTS, 
                max_concurrent_regions=MAX_CONCURRENT_REGIONS,
                account_ids=account_ids,
                ou_ids=ou_ids
            )
            logging.info(f"Retrieved {len(resources)} resources in total")
        except Exception as e:
            logging.error(f"Error occurred while getting resources: {str(e)}")
            logging.error(traceback.format_exc())
            resources = []
            accounts_with_many_resources = []
            
        if resources:
            logging.info(f"\n총 리소스 수: {len(resources)}")
            
            filename = get_csv_filename("aws_resources")
            
            save_to_csv(resources, filename)
            logging.info(f"결과가 {filename} 파일로 저장되었습니다.")

            for resource in resources[:10]:
                logging.info(resource['ARN'])
            
            if len(resources) >= 1000:
                print_resource_summary(resources, accounts_with_many_resources)
        else:
            logging.warning("No resources were retrieved. Check the logs for details.")
    
    elif search_option == '4':
        filename = safe_input("사용할 CSV 파일 이름을 입력하세요: ").strip()
        try:
            resources = read_csv_for_tagging(filename)
        except FileNotFoundError:
            logging.error(f"파일을 찾을 수 없습니다: {filename}")
            return
        except Exception as e:
            logging.error(f"CSV 파일 읽기 중 오류 발생: {str(e)}")
            return

    while True:
        print("\n1. 태그 추가")
        print("2. 태그 삭제")
        print("3. CSV에서 태그 추가")
        print("4. CSV에서 태그 삭제")
        print("5. 종료")
        action = safe_input("수행할 작업을 선택하세요 (1, 2, 3, 4, 또는 5): ")

        if action == '5':
            break
        if action in ['1', '2', '3', '4']:
            account_id = safe_input("태깅 대상 AWS 계정 ID를 입력하세요 (입력하지 않으면 모든 계정 대상): ").strip() or None
            region = safe_input("태깅 작업 대상 리전을 입력하세요 (입력하지 않으면 모든 리전 대상): ").strip() or None
            resource_type = safe_input("태깅 작업 대상 리소스 타입을 입력하세요 (입력하지 않으면 모든 리소스 타입 대상): ").strip() or None
            arn_filter = safe_input("ARN 필터를 입력하세요 (예: dev-hermes-bill-service, 입력하지 않으면 모든 ARN 대상): ").strip() or None

            if action == '1':
                tagged_resources = add_tags(session, resources, account_id, region, resource_type, arn_filter)
            elif action == '2':
                tagged_resources = remove_tags(session, resources, account_id, region, resource_type, arn_filter)
            elif action == '3':
                tagged_resources = add_tags_from_csv(session, resources, account_id, region, resource_type, arn_filter)
            elif action == '4':
                tagged_resources = remove_tags_from_csv(session, resources, account_id, region, resource_type, arn_filter)

            if tagged_resources:
                update_csv = safe_input("원본 CSV 파일을 업데이트하시겠습니까? (y/n): ").lower()
                if update_csv == 'y':
                    update_csv_with_tagged_resources(filename, tagged_resources)
                
                save_new_csv = safe_input("변경된 리소스를 별도의 CSV 파일로 저장하시겠습니까? (y/n): ").lower()
                if save_new_csv == 'y':
                    tagged_filename = get_csv_filename("tagged_resources")
                    save_tagged_resources_to_csv(tagged_resources, tagged_filename)
                    print(f"태그가 변경된 리소스가 {tagged_filename} 파일로 저장되었습니다.")
            else:
                print("태그가 변경된 리소스가 없습니다.")

        else:
            logging.info("잘못된 선택입니다.")
        if action in ['1', '2']:
            if resources:
                selected_resources = select_account_or_resource(resources)
                
                if not selected_resources:
                    logging.info("선택된 리소스가 없습니다.")
                    continue

                if action == '1':
                    tagged_resources = add_tags(session, selected_resources)
                elif action == '2':
                    tagged_resources = remove_tags(session, selected_resources)

            if tagged_resources:
                logging.info(f"태그가 변경된 리소스 수: {len(tagged_resources)}")
                print(f"총 {len(tagged_resources)}개의 리소스에 태그가 변경되었습니다.")
                update_csv = safe_input("원본 CSV 파일을 업데이트하시겠습니까? (y/n): ").lower()
                if update_csv == 'y':
                    update_csv_with_tagged_resources(filename, tagged_resources)
                    logging.info("사용자가 CSV 파일 업데이트를 선택했습니다.")
                    try:
                        update_csv_with_tagged_resources(filename, tagged_resources)
                        logging.info(f"원본 CSV 파일 '{filename}'이 성공적으로 업데이트되었습니다.")
                    except Exception as e:
                        logging.error(f"원본 CSV 파일 업데이트 중 오류 발생: {str(e)}")
                        print(f"원본 CSV 파일 업데이트 중 오류 발생: {str(e)}")
                else:
                    logging.info("사용자가 CSV 파일 업데이트를 선택하지 않았습니다.")
                
                save_new_csv = safe_input("수정된 리소스를 새 CSV 파일로 저장하시겠습니까? (y/n): ").lower()
                if save_new_csv == 'y':
                    tagged_filename = get_csv_filename("tagged_resources")
                    save_tagged_resources_to_csv(tagged_resources, tagged_filename)
                    logging.info("사용자가 새 CSV 파일 저장을 선택했습니다.")
                    try:
                        tagged_filename = get_csv_filename("tagged_resources")
                        save_tagged_resources_to_csv(tagged_resources, tagged_filename)
                        logging.info(f"태그가 변경된 리소스가 {tagged_filename} 파일로 저장되었습니다.")
                        print(f"태그가 변경된 리소스가 {tagged_filename} 파일로 저장되었습니다.")
                    except Exception as e:
                        logging.error(f"새 CSV 파일 저장 중 오류 발생: {str(e)}")
                        print(f"새 CSV 파일 저장 중 오류 발생: {str(e)}")
                else:
                    logging.info("사용자가 새 CSV 파일 저장을 선택하지 않았습니다.")
            else:
                logging.info("태그가 변경된 리소스가 없습니다.")
                print("태그가 변경된 리소스가 없습니다.")


        elif action in ['3', '4']:
            if 'filename' not in locals():
                filename = safe_input("참조할 CSV 파일 이름을 입력하세요: ")
                try:
                    resources = read_csv_for_tagging(filename)
                except FileNotFoundError:
                    print(f"Error: 파일 '{filename}'을 찾을 수 없습니다.")
                    continue
                except Exception as e:
                    print(f"CSV 파일 읽기 중 오류 발생: {str(e)}")
                    continue
            
            account_id = safe_input("태깅 대상 AWS 계정 ID를 입력하세요 (입력하지 않으면 모든 계정 대상): ").strip() or None
            region = safe_input("태깅 작업 대상 리전을 입력하세요 (입력하지 않으면 모든 리전 대상): ").strip() or None
            resource_type = safe_input("태깅 작업 대상 리소스 타입을 입력하세요 (입력하지 않으면 모든 리소스 타입 대상): ").strip() or None
            arn_filter = safe_input("ARN 필터를 입력하세요 (예: dev-hermes-bill-service, 입력하지 않으면 모든 ARN 대상): ").strip() or None

            if action == '3':
                tagged_resources = add_tags_from_csv(session, resources, account_id, region, resource_type, arn_filter)
            elif action == '4':
                tagged_resources = remove_tags_from_csv(session, resources, account_id, region, resource_type, arn_filter)

            if tagged_resources:
                update_csv = safe_input("원본 CSV 파일을 업데이트하시겠습니까? (y/n): ").lower()
                if update_csv == 'y':
                    update_csv_with_tagged_resources(filename, tagged_resources)
                
                save_new_csv = safe_input("수정된 리소스를 새 CSV 파일로 저장하시겠습니까? (y/n): ").lower()
                if save_new_csv == 'y':
                    tagged_filename = get_csv_filename("tagged_resources")
                    save_tagged_resources_to_csv(tagged_resources, tagged_filename)
                    print(f"태그가 변경된 리소스가 {tagged_filename} 파일로 저장되었습니다.")
            else:
                print("태그가 변경된 리소스가 없습니다.")

        else:
            logging.info("잘못된 선택입니다.")

def print_resource_summary(resources, accounts_with_many_resources):
    logging.info("\n전체 리소스가 1000개 이상입니다:")
    logging.info(f"총 리소스 수: {len(resources)}")
    logging.info("리소스 유형별 개수 (계정별):")
    
    resource_counts = defaultdict(lambda: defaultdict(int))
    for resource in resources:
        resource_type = resource['Resource Type']
        account_id = resource['Account ID']
        resource_counts[resource_type][account_id] += 1
    
    for resource_type, accounts in sorted(resource_counts.items(), key=lambda x: sum(x[1].values()), reverse=True):
        total_count = sum(accounts.values())
        logging.info(f"{resource_type}: {total_count}")
        for account_id, count in sorted(accounts.items(), key=lambda x: x[1], reverse=True):
            logging.info(f"  - Account {account_id}: {count}")
    
    if accounts_with_many_resources:
        logging.info("\n리소스가 1000개 이상인 계정:")
        for account_id, account_resources in accounts_with_many_resources:
            logging.info(f"\n계정 ID: {account_id}")
            logging.info(f"총 리소스 수: {len(account_resources)}")
            logging.info("리소스 유형별 개수:")
            account_resource_counts = defaultdict(int)
            for resource in account_resources:
                account_resource_counts[resource['Resource Type']] += 1
            for resource_type, count in sorted(account_resource_counts.items(), key=lambda x: x[1], reverse=True):
                logging.info(f"{resource_type}: {count}")

if __name__ == "__main__":
    main()