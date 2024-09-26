# config.py

# AWS SSO 프로필 이름 (필요한 경우)
SSO_PROFILE = 'shared'

# 검색할 리전 목록
REGIONS = ['ap-northeast-2']

# 태그 작업 시 사용할 역할 이름 (예: OrganizationAccountAccessRole)
ASSUME_ROLE_NAME = 'OrganizationAccountAccessRole'

# 리소스 검색 시 동시에 처리할 최대 계정 수
MAX_CONCURRENT_ACCOUNTS = 10

# 리소스 검색 시 동시에 처리할 최대 리전 수
MAX_CONCURRENT_REGIONS = 3

# 리트라이 설정
MAX_RETRIES = 10
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 60  # seconds