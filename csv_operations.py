# csv_operations.py
# CSV 를 읽고 쓰는 행위들에 대해 정의
import csv
import tempfile
import os
import logging

from typing import List, Dict

def save_to_csv(resources: List[Dict], filename: str) -> None:
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['ARN', 'Service', 'Resource Type', 'Region', 'Account ID', 'Tags', 'Create Date']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for resource in resources:
            writer.writerow({
                'ARN': resource['ARN'],
                'Service': resource['Service'],
                'Resource Type': resource['Resource Type'],
                'Region': resource['Region'],
                'Account ID': resource['Account ID'],
                'Tags': str(resource['Tags']),
                'Create Date': resource.get('Create Date', 'Unknown')
            })

def save_tagged_resources_to_csv(resources: List[Dict], filename: str) -> None:
    save_to_csv(resources, filename)

def read_csv_for_tagging(filename: str) -> List[Dict]:
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            return list(reader)
    except FileNotFoundError:
        raise FileNotFoundError(f"파일 '{filename}'을 찾을 수 없습니다.")
    except csv.Error as e:
        raise ValueError(f"CSV 파일 '{filename}'을 읽는 중 오류가 발생했습니다: {str(e)}")
    except Exception as e:
        raise Exception(f"파일 '{filename}'을 읽는 중 예기치 않은 오류가 발생했습니다: {str(e)}")

def update_csv_with_tagged_resources(filename: str, tagged_resources: List[Dict]):
    logging.info(f"Updating CSV file: {filename}")
    logging.info(f"Number of tagged resources: {len(tagged_resources)}")
    
    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, newline='', encoding='utf-8')
    
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as csvfile, temp_file:
            reader = csv.DictReader(csvfile)
            fieldnames = reader.fieldnames
            if 'Create Date' not in fieldnames:
                fieldnames.append('Create Date')

            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()

            updated_count = 0
            for row in reader:
                # 태그가 수정된 리소스 찾기
                matching_resource = next((r for r in tagged_resources if r['ARN'] == row['ARN']), None)
                if matching_resource:
                    row['Tags'] = str(matching_resource['Tags'])
                    row['Create Date'] = matching_resource.get('Create Date', 'Unknown')
                    updated_count += 1
                elif 'Create Date' not in row:
                    row['Create Date'] = 'Unknown'
                writer.writerow(row)

        # 임시 파일을 원본 파일로 대체
        os.replace(temp_file.name, filename)
        logging.info(f"원본 CSV 파일 '{filename}'이 성공적으로 업데이트되었습니다. 업데이트된 행 수: {updated_count}")
        print(f"원본 CSV 파일 '{filename}'이 성공적으로 업데이트되었습니다.")
    
    except Exception as e:
        logging.error(f"CSV 파일 업데이트 중 오류 발생: {str(e)}")
        print(f"CSV 파일 업데이트 중 오류 발생: {str(e)}")
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
    
    except FileNotFoundError:
        print(f"오류: 파일 '{filename}'을 찾을 수 없습니다.")
    except csv.Error as e:
        print(f"CSV 오류: {str(e)}")
    except Exception as e:
        print(f"예기치 않은 오류: {str(e)}")
    finally:
        # 오류 발생 시 임시 파일 삭제
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)