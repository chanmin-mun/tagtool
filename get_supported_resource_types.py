#다른 메인 기능들과 상관 없이, 별도로 Config 를 통해 불러 올 수 있는 서비스들을 나열. SSO Profile 및 Region 정보 필요 (ex: python get_supported_resource_types.py --profile shared --region ap-northeast-2 )
import boto3
import argparse

def get_discovered_resource_types(session, region):
    config_client = session.client('config', region_name=region)
    
    try:
        response = config_client.get_discovered_resource_counts()
        resource_types = [item['resourceType'] for item in response['resourceCounts']]
        return sorted(resource_types)
    except config_client.exceptions.NoAvailableConfigurationRecorderException:
        print("Error: AWS Config is not enabled in this region.")
        return []

def main():
    parser = argparse.ArgumentParser(description='Get discovered resource types from AWS Config')
    parser.add_argument('--profile', default='default', help='AWS profile name')
    parser.add_argument('--region', default='ap-northeast-2', help='AWS region')
    args = parser.parse_args()

    try:
        session = boto3.Session(profile_name=args.profile)
        discovered_types = get_discovered_resource_types(session, args.region)

        if discovered_types:
            print(f"Discovered resource types in region {args.region}:")
            for resource_type in discovered_types:
                print(f"- {resource_type}")
        else:
            print("No resource types discovered or AWS Config is not enabled.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()