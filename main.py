import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import datetime
import os
import json
import time

# --- 설정값 ---
NAVER_ID = os.environ.get('NAVER_ID')
NAVER_SECRET = os.environ.get('NAVER_SECRET')
GOOGLE_JSON = os.environ.get('GOOGLE_JSON')
TARGET_KEYWORD = "올리브영" # 검색 키워드

def connect_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(GOOGLE_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("뉴스수집").sheet1

def get_news(keyword):
    # 중복 보충을 위해 한 번에 100개를 가져오도록 설정 (최대치)
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=100&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    res = requests.get(url, headers=headers)
    return res.json().get('items', []) if res.status_code == 200 else []

def get_details(link):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        if "news.naver.com" not in link: return "외부링크", "확인필요"
        res = requests.get(link, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        media = soup.select_one("img.media_end_head_top_logo_img")['title'] if soup.select_one("img.media_end_head_top_logo_img") else "정보없음"
        reporter = soup.select_one("span.byline_s").text.strip() if soup.select_one("span.byline_s") else "정보없음"
        return media, reporter
    except: return "접속실패", "확인불가"

def analyze_sentiment(text):
    pos = ['상승','호재','급등','성장','기대','최고','개선','돌파','수주','신기록']
    neg = ['하락','악재','급락','우려','손실','위기','둔화','감소','영업이익 감소','쇼크']
    score = sum([1 for w in pos if w in text]) - sum([1 for w in neg if w in text])
    return "긍정" if score > 0 else ("부정" if score < 0 else "중립")

def job():
    sheet = connect_google_sheet()
    
    # 1. 시트에 이미 저장된 링크들 가져오기 (중복 제거용)
    # 기사가 많아지면 최근 500개 정도만 확인하도록 설정
    existing_links = sheet.col_values(5) # 5번째 열이 링크 열입니다.
    
    news_list = get_news(TARGET_KEYWORD)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    new_rows = []
    # 네이버는 최신순으로 주므로, 과거 순서대로 쌓기 위해 리스트를 뒤집습니다.
    for item in reversed(news_list):
        title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"')
        link = item['originallink'] or item['link']
        
        # 2. 중복 체크: 이미 시트에 있는 링크라면 건너뜁니다.
        if link in existing_links:
            continue
            
        media, reporter = get_details(link)
        sentiment = analyze_sentiment(title)
        
        new_rows.append([current_time, media, reporter, title, link, "확인불가", sentiment])
        time.sleep(0.1) # 차단 방지를 위한 미세한 간격

    # 3. 새로운 기사만 한꺼번에 추가
    if new_rows:
        sheet.append_rows(new_rows)
        print(f"{len(new_rows)}개의 새로운 기사를 추가했습니다.")
    else:
        print("새로 추가할 기사가 없습니다.")

if __name__ == "__main__":
    job()
