# tagging_operations.py
# 실제 태깅 하는 기능을 정의
import boto3
import botocore
import logging
import traceback
import sys
import io
from typing import List, Dict
from utils import safe_input


sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

def add_tags(session, selected_resources: List[Dict], account_id: str = None, region: str = None, resource_type: str = None, arn_filter: str = None) -> List[Dict]:
    tag_key = safe_input("추가할 태그 키를 입력하세요: ").strip()
    tag_value = safe_input("추가할 태그 값을 입력하세요 (빈 값도 가능): ").strip()
    if not tag_key:
        logging.error("태그 키는 비어있을 수 없습니다.")
        return []

    tagged_resources = []
    for resource in selected_resources:
        if ((account_id is None or resource['Account ID'] == account_id) and 
            (region is None or resource['Region'] == region) and 
            (resource_type is None or resource['Resource Type'] == resource_type) and
            (arn_filter is None or arn_filter in resource['ARN'])):
            try:
                assumed_session = assume_role(session, resource['Account ID'], "OrganizationAccountAccessRole")
                client = assumed_session.client('resourcegroupstaggingapi', region_name=resource['Region'])
                response = client.tag_resources(
                    ResourceARNList=[resource['ARN']],
                    Tags={tag_key: tag_value}
                )
                if response.get('FailedResourcesMap'):
                    logging.error(f"리소스 {resource['ARN']}에 태그 추가 실패: {response['FailedResourcesMap']}")
                else:
                    logging.info(f"리소스 {resource['ARN']}에 태그 추가 성공")
                    resource['Tags'] = resource.get('Tags', {})
                    resource['Tags'][tag_key] = tag_value
                    tagged_resources.append(resource)
            except Exception as e:
                logging.error(f"리소스 {resource['ARN']}에 태그 추가 중 오류 발생: {str(e)}")

    logging.info(f"총 {len(tagged_resources)}개의 리소스에 태그가 추가되었습니다.")
    return tagged_resources


def remove_tags(session, selected_resources: List[Dict], account_id: str = None, region: str = None, resource_type: str = None, arn_filter: str = None) -> List[Dict]:
    tag_key = safe_input("삭제할 태그 키를 입력하세요: ")

    tagged_resources = []
    for resource in selected_resources:
        if ((account_id is None or resource['Account ID'] == account_id) and 
            (region is None or resource['Region'] == region) and 
            (resource_type is None or resource['Resource Type'] == resource_type) and
            (arn_filter is None or arn_filter in resource['ARN'])):
            try:
                assumed_session = assume_role(session, resource['Account ID'], "OrganizationAccountAccessRole")
                client = assumed_session.client('resourcegroupstaggingapi', region_name=resource['Region'])
                response = client.untag_resources(
                    ResourceARNList=[resource['ARN']],
                    TagKeys=[tag_key]
                )
                if response['FailedResourcesMap']:
                    logging.error(f"리소스 {resource['ARN']}에서 태그 삭제 실패: {response['FailedResourcesMap']}")
                else:
                    logging.info(f"리소스 {resource['ARN']}에서 태그 삭제 성공")
                    resource['Tags'] = resource.get('Tags', {})
                    if tag_key in resource['Tags']:
                        del resource['Tags'][tag_key]
                    tagged_resources.append(resource)
            except Exception as e:
                logging.error(f"리소스 {resource['ARN']}에서 태그 삭제 중 오류 발생: {str(e)}")

    return tagged_resources

def add_tags_from_csv(session, resources: List[Dict], account_id: str = None, region: str = None, resource_type: str = None, arn_filter: str = None) -> List[Dict]:
    tag_key = safe_input("추가할 태그 키를 입력하세요: ").strip()
    tag_value = safe_input("추가할 태그 값을 입력하세요 (빈 값도 가능): ").strip()
    if not tag_key:
        logging.error("태그 키는 비어있을 수 없습니다.")
        return []

    tagged_resources = []
    matching_resources = 0
    resources_to_tag = 0
    for resource in resources:
        if ((account_id is None or resource['Account ID'] == account_id) and 
            (region is None or resource['Region'] == region or resource['Region'] == 'global') and 
            (resource_type is None or resource['Resource Type'] == resource_type) and
            (arn_filter is None or arn_filter in resource['ARN'])):
            matching_resources += 1
            
            # 현재 태그 확인
            current_tags = resource['Tags']
            if isinstance(current_tags, str):
                try:
                    current_tags = eval(current_tags)
                except:
                    current_tags = {}
            elif not isinstance(current_tags, dict):
                current_tags = {}
            
            # 태그가 존재하지 않거나 다른 값을 가진 경우에만 추가
            if tag_key not in current_tags or current_tags[tag_key] != tag_value:
                resources_to_tag += 1
                try:
                    assumed_session = assume_role(session, resource['Account ID'], "OrganizationAccountAccessRole")
                    client = assumed_session.client('resourcegroupstaggingapi', region_name=resource['Region'])
                    response = client.tag_resources(
                        ResourceARNList=[resource['ARN']],
                        Tags={tag_key: tag_value}
                    )
                    if response.get('FailedResourcesMap'):
                        logging.error(f"리소스 {resource['ARN']}에 태그 추가 실패: {response['FailedResourcesMap']}")
                    else:
                        logging.info(f"리소스 {resource['ARN']}에 태그 추가 성공")
                        current_tags[tag_key] = tag_value
                        resource['Tags'] = current_tags  # 여기서 딕셔너리를 다시 할당
                        tagged_resources.append(resource)
                except Exception as e:
                    logging.error(f"리소스 {resource['ARN']}에 태그 추가 중 오류 발생: {str(e)}")
                    logging.error(traceback.format_exc())

    logging.info(f"총 {matching_resources}개의 리소스가 조건과 일치합니다.")
    logging.info(f"그 중 {resources_to_tag}개의 리소스에 태그를 추가해야 했습니다.")
    logging.info(f"총 {len(tagged_resources)}개의 리소스에 태그가 추가되었습니다.")

    if matching_resources == 0:
        logging.warning(f"입력한 조건 (계정 ID: {account_id or '모든 계정'}, 리전: {region or '모든 리전'}, 리소스 타입: {resource_type or '모든 타입'}, ARN 필터: {arn_filter or '없음'})과 일치하는 리소스가 없습니다.")
    elif len(tagged_resources) == 0:
        logging.warning("일치하는 리소스가 있지만 태그 추가에 실패했습니다. 위의 오류 메시지를 확인해주세요.")

    return tagged_resources   

def remove_tags_from_csv(session, resources: List[Dict], account_id: str = None, region: str = None, resource_type: str = None, arn_filter: str = None) -> List[Dict]:
    tag_key = safe_input("삭제할 태그 키를 입력하세요: ")

    tagged_resources = []
    matching_resources = 0
    resources_with_tag = 0
    for resource in resources:
        if ((account_id is None or resource['Account ID'] == account_id) and 
            (region is None or resource['Region'] == region or resource['Region'] == 'global') and 
            (resource_type is None or resource['Resource Type'] == resource_type) and
            (arn_filter is None or arn_filter in resource['ARN'])):
            matching_resources += 1
            
            # 태그가 존재하는지 확인
            current_tags = resource['Tags']
            if isinstance(current_tags, str):
                try:
                    current_tags = eval(current_tags)
                except:
                    current_tags = {}
            elif not isinstance(current_tags, dict):
                current_tags = {}
            
            if tag_key in current_tags:
                resources_with_tag += 1
                try:
                    assumed_session = assume_role(session, resource['Account ID'], "OrganizationAccountAccessRole")
                    client = assumed_session.client('resourcegroupstaggingapi', region_name=resource['Region'])
                    response = client.untag_resources(
                        ResourceARNList=[resource['ARN']],
                        TagKeys=[tag_key]
                    )
                    if response['FailedResourcesMap']:
                        logging.error(f"리소스 {resource['ARN']}에서 태그 삭제 실패: {response['FailedResourcesMap']}")
                    else:
                        logging.info(f"리소스 {resource['ARN']}에서 태그 삭제 성공")
                        del current_tags[tag_key]
                        resource['Tags'] = current_tags
                        tagged_resources.append(resource)
                except Exception as e:
                    logging.error(f"리소스 {resource['ARN']}에서 태그 삭제 중 오류 발생: {str(e)}")
                    logging.error(traceback.format_exc())

    logging.info(f"총 {matching_resources}개의 리소스가 조건과 일치합니다.")
    logging.info(f"그 중 {resources_with_tag}개의 리소스에 삭제할 태그가 있었습니다.")
    logging.info(f"총 {len(tagged_resources)}개의 리소스에서 태그가 삭제되었습니다.")

    if matching_resources == 0:
        warning_msg = f"입력한 조건 (계정 ID: {account_id or '모든 계정'}, 리전: {region or '모든 리전'}, 리소스 타입: {resource_type or '모든 타입'}, ARN 필터: {arn_filter or '없음'})과 일치하는 리소스가 없습니다."
        logging.warning(warning_msg)
        print(warning_msg)  # 콘솔에 직접 출력
    elif len(tagged_resources) == 0:
        warning_msg = "일치하는 리소스가 있지만 태그 삭제에 실패했습니다. 위의 오류 메시지를 확인해주세요."
        logging.warning(warning_msg)
        print(warning_msg)  # 콘솔에 직접 출력

    return tagged_resources


def assume_role(session, account_id, role_name):
    sts_client = session.client('sts')
    assumed_role_object = sts_client.assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/{role_name}",
        RoleSessionName="AssumeRoleSession1"
    )
    credentials = assumed_role_object['Credentials']
    return boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken'],
    )