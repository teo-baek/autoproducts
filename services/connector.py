import urllib.request
import json
import re

class DriveConnector:
    def __init__(self, gas_url="https://script.google.com/macros/s/AKfycbwkKOJJeZX75jmWXP-gaXw__cyec6tXxKYQ8cxp8Ou5emWvXhN6KedCH0j3mkZPcl3L1w/exec"):
        self.gas_url = gas_url

    def get_file_list(self, folder_id):
        """Google Apps Script 웹 앱을 통해 구글 드라이브 폴더 내 파일명과 ID 목록을 안정적으로 가져오는 함수"""
        file_map = {}
        try:
            req_url = f"{self.gas_url}?folderId={folder_id}"
            req = urllib.request.Request(req_url)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                for f_name, f_id in data.items():
                    # 확장자 제거 (예: product.jpg -> product)
                    clean_name = re.sub(r'\.[a-zA-Z0-9]+$', '', f_name)
                    # 포스기 품번 형태에 맞춰 .0 오차 제거 및 공백 제거
                    clean_key = re.sub(r'\.0$', '', clean_name.strip())
                    file_map[clean_key] = f_id
        except Exception as e:
            print(f"DriveConnector Error: {e}")
            pass
        return file_map
