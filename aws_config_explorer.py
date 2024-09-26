# aws_config_explorer.py
#AWS Config 서비스를 사용해 명시된 Resource 정보를 가져옴
import boto3
import botocore
from typing import List, Dict, Tuple
import logging
import concurrent.futures
import time
import random
import traceback
from datetime import datetime, timezone

def exponential_backoff(retry_count):
    return min(2 ** retry_count + random.random(), 60)

def get_accounts_in_ous(org_client, ou_ids):
    accounts = []
    for ou_id in ou_ids:
        paginator = org_client.get_paginator('list_accounts_for_parent')
        for page in paginator.paginate(ParentId=ou_id):
            for account in page['Accounts']:
                if account['Status'] == 'ACTIVE':
                    accounts.append(account['Id'])
    return list(set(accounts))  # 중복 제거

def get_all_ou_ids(org_client):
    ou_ids = []
    paginator = org_client.get_paginator('list_roots')
    for page in paginator.paginate():
        for root in page['Roots']:
            ou_ids.extend(get_child_ous(org_client, root['Id']))
    return ou_ids

def get_child_ous(org_client, parent_id):
    child_ous = []
    paginator = org_client.get_paginator('list_organizational_units_for_parent')
    for page in paginator.paginate(ParentId=parent_id):
        for ou in page['OrganizationalUnits']:
            child_ous.append((ou['Id'], ou['Name']))
            child_ous.extend(get_child_ous(org_client, ou['Id']))
    return child_ous

def get_all_accounts(org_client):
    accounts = []
    paginator = org_client.get_paginator('list_accounts')
    for page in paginator.paginate():
        for account in page['Accounts']:
            if account['Status'] == 'ACTIVE':
                accounts.append((account['Id'], account['Name']))
    return accounts

def get_resource_config_with_retry(config_client, resource_type, resource_id, account_id, region, max_retries=5):
    for retry in range(max_retries):
        try:
            config_items = config_client.get_resource_config_history(
                resourceType=resource_type,
                resourceId=resource_id,
                limit=1,
                earlierTime=datetime(1970, 1, 1, tzinfo=timezone.utc)  # datetime 모듈 사용
            )['configurationItems']
            
            if config_items:
                return config_items[0]
            else:
                raise Exception(f"No configuration items found for {resource_type}:{resource_id}")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                if retry == max_retries - 1:
                    raise
                sleep_time = exponential_backoff(retry)
                logging.warning(f"Throttling occurred for {resource_type}:{resource_id} in account {account_id}, region {region}. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                raise

def get_resources_from_config(session, account_id: str, region: str) -> List[Dict]:
    config_client = session.client('config', region_name=region)
    all_resources = []
    
    supported_resource_types = get_supported_resource_types(session, region)
    print(f"Supported resource types in account {account_id}, region {region}: {supported_resource_types}")

    total_resources_count = 0

    for resource_type in supported_resource_types:
        try:
            print(f"Fetching {resource_type} resources in account {account_id}, region {region}")
            paginator = config_client.get_paginator('list_discovered_resources')
            resources_count = 0
            for page in paginator.paginate(resourceType=resource_type):
                for resource in page['resourceIdentifiers']:
                    try:
                        resource_detail = get_resource_config_with_retry(
                            config_client,
                            resource['resourceType'],
                            resource['resourceId'],
                            account_id,
                            region
                        )
                        
                        # 생성 날짜 추출
                        create_date = resource_detail.get('resourceCreationTime')
                        if create_date:
                            create_date = create_date.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            create_date = 'Unknown'

                        all_resources.append({
                            'ARN': resource_detail.get('arn', ''),
                            'Service': resource_detail['resourceType'].split('::')[1].lower(),
                            'Resource Type': resource_detail['resourceType'],
                            'Region': region,
                            'Account ID': account_id,
                            'Tags': resource_detail.get('tags', {}),
                            'Create Date': create_date
                        })
                        resources_count += 1
                        total_resources_count += 1
                        if resources_count % 10 == 0:
                            print(f"{resources_count} {resource_type} resources 가져오는중")
                    except Exception as e:
                        print(f"Error processing resource {resource['resourceType']}:{resource['resourceId']} in account {account_id}, region {region}: {str(e)}")
                        continue
            print(f"Fetched total {resources_count} {resource_type} resources in account {account_id}, region {region}")
        except Exception as e:
            print(f"Error fetching {resource_type} in account {account_id}, region {region}: {str(e)}")
    
    print(f"Total resources fetched for account {account_id} in region {region}: {total_resources_count}")
    return all_resources

#Exception 났을 때 Retry 처리 하기 위한 함수
def get_resource_config_with_retry(config_client, resource_type, resource_id, account_id, region, max_retries=5):
    for retry in range(max_retries):
        try:
            config_items = config_client.get_resource_config_history(
                resourceType=resource_type,
                resourceId=resource_id,
                limit=1,  # 가장 최근의 구성 항목만 가져옵니다
                earlierTime=datetime(1970, 1, 1, tzinfo=timezone.utc)  # 가능한 가장 이른 시간부터 조회
            )['configurationItems']
            
            if config_items:
                return config_items[0]
            else:
                raise Exception(f"No configuration items found for {resource_type}:{resource_id}")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'ThrottlingException':
                if retry == max_retries - 1:
                    raise
                sleep_time = exponential_backoff(retry)
                logging.warning(f"Throttling occurred for {resource_type}:{resource_id} in account {account_id}, region {region}. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_resource_type = {executor.submit(process_resource_type, rt): rt for rt in resource_types}
        for future in concurrent.futures.as_completed(future_to_resource_type):
            resource_type = future_to_resource_type[future]
            try:
                all_resources.extend(future.result())
            except Exception as exc:
                logging.error(f'{resource_type} generated an exception: {exc}')
    
    return all_resources

def get_all_resources(session, regions, assume_role_name="OrganizationAccountAccessRole", 
                      max_concurrent_accounts=30, max_concurrent_regions=3, 
                      account_ids=None, ou_ids=None):
    try:
        org_client = session.client('organizations')
        
        if account_ids:
            target_accounts = account_ids
        elif ou_ids:
            target_accounts = get_accounts_in_ous(org_client, ou_ids)
        else:
            target_accounts = [account[0] for account in get_all_accounts(org_client)]

        print("Target accounts:")
        for account in target_accounts:
            print(f"  {account}")
        
        print(f"Processing {len(target_accounts)} accounts")

        all_resources = []
        accounts_with_many_resources = []

        def process_account(account_id):
            print(f"Processing account: {account_id}")
            account_resources = []
            for region in regions:
                try:
                    print(f"Processing account {account_id} in region {region}")
                    assumed_session = assume_role(session, account_id, assume_role_name)
                    resources = get_resources_from_config(assumed_session, account_id, region)
                    account_resources.extend(resources)
                    print(f"Retrieved {len(resources)} resources from account {account_id} in region {region}")
                except Exception as e:
                    print(f"Error processing account {account_id} in region {region}: {str(e)}")
                    print(traceback.format_exc())
            return account_id, account_resources

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_accounts) as executor:
            future_to_account = {executor.submit(process_account, account_id): account_id for account_id in target_accounts}
            completed_accounts = 0
            for future in concurrent.futures.as_completed(future_to_account):
                account_id = future_to_account[future]
                try:
                    account_id, resources = future.result()
                    all_resources.extend(resources)
                    if len(resources) >= 1000:
                        accounts_with_many_resources.append((account_id, resources))
                    completed_accounts += 1
                    print(f"Completed processing {completed_accounts}/{len(target_accounts)} accounts")
                except Exception as e:
                    print(f"Error processing account {account_id}: {str(e)}")
                    print(traceback.format_exc())

        print(f"Total resources retrieved: {len(all_resources)}")
        return all_resources, accounts_with_many_resources
    except Exception as e:
        print(f"Error in get_all_resources: {str(e)}")
        print(traceback.format_exc())
        return [], []

def assume_role(session, account_id, role_name):
    sts_client = session.client('sts')
    try:
        if isinstance(account_id, tuple):
            account_id = account_id[0]
        
        account_id = str(account_id)

        if not account_id.isdigit() or len(account_id) != 12:
            raise ValueError(f"Invalid account ID: {account_id}")
        
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        print(f"Attempting to assume role: {role_arn}")
        
        assumed_role_object = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="AssumeRoleSession1"
        )
        credentials = assumed_role_object['Credentials']
        
        print(f"Successfully assumed role for account {account_id}")
        
        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
        )
    except Exception as e:
        print(f"Error assuming role for account {account_id}: {str(e)}")
        print(f"Role ARN: {role_arn}")
        print(traceback.format_exc())
        raise

def get_supported_resource_types(session, region: str) -> List[str]:
    config_client = session.client('config', region_name=region)
    response = config_client.describe_configuration_recorder_status()
    
    if not response['ConfigurationRecordersStatus']:
        logging.warning("AWS Config is not enabled in this account/region.")
        return []
    
    resource_types = config_client.get_discovered_resource_counts()['resourceCounts']
    
    return [item['resourceType'] for item in resource_types]