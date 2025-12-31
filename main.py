import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
import datetime
import os
import json

# --- 설정값 (깃허브가 관리해줌) ---
NAVER_ID = os.environ.get('NAVER_ID')
NAVER_SECRET = os.environ.get('NAVER_SECRET')
GOOGLE_JSON = os.environ.get('GOOGLE_JSON')
TARGET_KEYWORD = "올리브영" # <-- 여기를 원하는 검색어로 바꾸세요!

# --- 1. 구글 시트 연결 ---
def connect_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(GOOGLE_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # 구글 시트 이름을 꼭 '뉴스수집'으로 만들어주세요 (아니면 아래 이름을 시트 제목과 똑같이 수정)
    return client.open("뉴스수집").sheet1

# --- 2. 네이버 뉴스 검색 ---
def get_news(keyword):
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=10&sort=date"
    headers = {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return res.json().get('items', [])
    return []

# --- 3. 상세 정보 크롤링 ---
def get_details(link):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 네이버 뉴스(news.naver.com)인 경우만 시도
        if "news.naver.com" not in link:
            return "외부링크", "확인필요"
            
        res = requests.get(link, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 매체명 추출 시도
        try: media = soup.select_one("img.media_end_head_top_logo_img")['title']
        except: media = "정보없음"
            
        # 기자명 추출 시도
        try: reporter = soup.select_one("span.byline_s").text.strip()
        except: reporter = "정보없음"
            
        return media, reporter
    except:
        return "접속실패", "확인불가"

# --- 4. 긍정/부정 판단 ---
def analyze_sentiment(text):
    positive = ['상승', '호재', '급등', '성장', '기대', '최고', '개선', '돌파']
    negative = ['하락', '악재', '급락', '우려', '손실', '위기', '둔화', '감소']
    
    score = 0
    for w in positive:
        if w in text: score += 1
    for w in negative:
        if w in text: score -= 1
        
    if score > 0: return "긍정"
    elif score < 0: return "부정"
    else: return "중립"

# --- 실행 로직 ---
def job():
    print(f"[{datetime.datetime.now()}] 뉴스 수집 시작: {TARGET_KEYWORD}")
    try:
        sheet = connect_google_sheet()
        news_list = get_news(TARGET_KEYWORD)
        
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        count = 0
        for item in news_list:
            title = item['title'].replace('<b>', '').replace('</b>', '').replace('&quot;', '"')
            link = item['originallink'] or item['link']
            
            # 상세 정보 가져오기
            media, reporter = get_details(link)
            # 감성 분석
            sentiment = analyze_sentiment(title)
            
            # 시트에 추가할 행 데이터
            row = [
                current_time, 
                media, 
                reporter, 
                title, 
                link, 
                "확인불가", 
                sentiment
            ]
            sheet.append_row(row)
            count += 1
            
        print(f"총 {count}개의 뉴스를 저장했습니다.")
        
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    job()