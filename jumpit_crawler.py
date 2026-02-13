import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import json
import re
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

class JumpitCrawler:
    """점핏(jumpit.saramin.co.kr) 채용 공고 크롤러"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://jumpit.saramin.co.kr/',
        }
        self.jumpit_base_url = "https://jumpit.saramin.co.kr"
        self.jumpit_positions_url = f"{self.jumpit_base_url}/positions"

        # 개발 직무 탐색 (점핏 사이트 직무 필터 값)
        self.jumpit_job_roles = {
            '전체': None,
            '서버/백엔드 개발자': 'backend',
            '프론트엔드 개발자': 'frontend',
            '웹 풀스택 개발자': 'fullstack',
            '안드로이드 개발자': 'android',
            'iOS 개발자': 'ios',
            '크로스플랫폼 앱개발자': 'crossplatform',
            '게임 클라이언트 개발자': 'game-client',
            '게임 서버 개발자': 'game-server',
            'DBA': 'dba',
            '빅데이터 엔지니어': 'bigdata',
            '인공지능/머신러닝': 'ai-ml',
            'devops/시스템 엔지니어': 'devops',
            '정보보안 담당자': 'security',
            'QA 엔지니어': 'qa',
            '개발 PM': 'pm',
            'HW/임베디드': 'embedded',
            'SW/솔루션': 'solution',
            '웹퍼블리셔': 'webpub',
            'VR/AR/3D': 'vr-ar',
            '블록체인': 'blockchain',
            '기술지원': 'tech-support',
        }

    def search_jobs_jumpit(self, sort='popular', max_pages=30, job_role='전체', target_count=None):
        """점핏 positions 페이지에서 채용 공고 크롤링. target_count 지정 시 해당 개수 채울 때까지 연속 페이지 수집."""
        jobs = []
        url = self.jumpit_positions_url
        params = {'sort': sort}
        role_param = self.jumpit_job_roles.get(job_role) if job_role else None
        if role_param:
            params['job'] = role_param
        use_playwright = False

        try:
            page = 1
            seen_links = set()
            while page <= max_pages:
                if page > 1:
                    params['page'] = page
                role_label = f", 직무={job_role}" if job_role else ""
                unique_so_far = len(seen_links)
                print(f"📄 점핏 positions {page} 페이지 수집 중... (sort={sort}{role_label}) [고유 {unique_so_far}개]")

                html = None
                if use_playwright and HAS_PLAYWRIGHT:
                    html = self._fetch_html_with_playwright(url, params)
                else:
                    response = requests.get(url, params=params, headers=self.headers)
                    response.raise_for_status()
                    html = response.text

                next_data = self._parse_next_data(html or '')
                page_jobs = []
                if next_data:
                    page_jobs = self._extract_jobs_from_jumpit_data(next_data, job_role=job_role or '전체')
                if not page_jobs and page == 1:
                    next_data = self._fetch_next_data_url(params)
                    if next_data:
                        page_jobs = self._extract_jobs_from_jumpit_data(next_data, job_role=job_role or '전체')
                if not page_jobs and page == 1 and HAS_PLAYWRIGHT:
                    print("   └─ 브라우저(Playwright)로 페이지 로드 중...")
                    html = self._fetch_html_with_playwright(url, params)
                    if html:
                        next_data = self._parse_next_data(html)
                        if next_data:
                            page_jobs = self._extract_jobs_from_jumpit_data(next_data, job_role=job_role or '전체')
                        if not page_jobs:
                            page_jobs = self._extract_jobs_from_jumpit_html(html, job_role=job_role or '전체')
                        if page_jobs:
                            use_playwright = True
                if not page_jobs:
                    page_jobs = self._extract_jobs_from_jumpit_html(html or '', job_role=job_role or '전체')

                if page_jobs:
                    jobs.extend(page_jobs)
                    for j in page_jobs:
                        link = j.get('link')
                        if link:
                            seen_links.add(link)
                    unique_so_far = len(seen_links)
                    print(f"   └─ {len(page_jobs)}개 수집 (고유 {unique_so_far}개)")
                    if target_count and unique_so_far >= target_count:
                        print(f"   → 목표 고유 {target_count}개 도달, 리스트 수집 종료")
                        break
                else:
                    if page == 1:
                        if not HAS_PLAYWRIGHT:
                            print("   ⚠️ 데이터 없음. pip install playwright 후 playwright install chromium 실행하세요.")
                        else:
                            print("   ⚠️ 브라우저 로드 후에도 데이터를 찾지 못했습니다.")
                    break

                page += 1
                time.sleep(1)

            print(f"✅ 점핏 '{job_role or "전체"}' (sort={sort}) 총 {len(jobs)}개 공고 수집 완료!")
        except Exception as e:
            print(f"❌ 점핏 크롤링 실패: {e}")
            return []

        return jobs

    def _parse_next_data(self, html):
        """HTML에서 __NEXT_DATA__ 또는 유사 JSON 블록 추출"""
        soup = BeautifulSoup(html, 'html.parser')
        script = soup.find('script', id='__NEXT_DATA__')
        if script and script.string:
            try:
                return json.loads(script.string)
            except json.JSONDecodeError:
                pass
        for s in soup.find_all('script', type='application/json'):
            if s.string and ('position' in s.string.lower() or 'recruit' in s.string.lower()):
                try:
                    return json.loads(s.string)
                except json.JSONDecodeError:
                    continue
        return None

    def _fetch_next_data_url(self, params):
        """Next.js _next/data API로 포지션 데이터 직접 요청 (buildId 추출 후)"""
        try:
            r = requests.get(
                self.jumpit_positions_url,
                params={k: v for k, v in params.items() if k != 'page'},
                headers=self.headers,
            )
            r.raise_for_status()
            html = r.text
            data = self._parse_next_data(html)
            build_id = None
            if data and data.get('buildId'):
                build_id = data['buildId']
            if not build_id:
                build_match = re.search(r'/_next/data/([a-zA-Z0-9_-]+)/', html)
                if build_match:
                    build_id = build_match.group(1)
            if build_id:
                data_url = f"{self.jumpit_base_url}/_next/data/{build_id}/positions.json"
                resp = requests.get(data_url, params=params, headers={**self.headers, 'Accept': 'application/json'})
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            print(f"   ⚠️ _next/data 요청 실패: {e}")
        return None

    def _fetch_html_with_playwright(self, base_url, params, timeout=20000):
        """Playwright로 페이지를 렌더링한 뒤 HTML 반환 (JS 로드 대기)"""
        if not HAS_PLAYWRIGHT:
            return None
        from urllib.parse import urlencode
        qs = urlencode(params)
        url = f"{base_url}?{qs}" if qs else base_url
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                page.wait_for_selector('a[href*="/position/"]', timeout=timeout)
                html = page.content()
                browser.close()
            return html
        except Exception as e:
            print(f"   ⚠️ Playwright 로드 실패: {e}")
            return None

    def _fetch_jobs_list_infinite_scroll_playwright(self, target_count=200, job_role='전체', sort='popular'):
        """무한 스크롤 리스트 페이지에서 target_count개 카드가 로드될 때까지 스크롤 후 카드 목록 수집."""
        if not HAS_PLAYWRIGHT:
            return []
        from urllib.parse import urlencode
        params = {'sort': sort}
        role_param = self.jumpit_job_roles.get(job_role) if job_role else None
        if role_param:
            params['job'] = role_param
        list_url = self.jumpit_positions_url + ('?' + urlencode(params) if params else '')
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(list_url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_selector('a[href*="/position/"]', timeout=15000)
                print(f"\n📜 무한 스크롤: 최소 {target_count}개 카드 로드될 때까지 스크롤 중...")
                max_scrolls = 40
                scroll_pause_sec = 1.5
                for scroll_num in range(max_scrolls):
                    prev_height = page.evaluate("document.body.scrollHeight")
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(scroll_pause_sec)
                    links = page.evaluate("""() => {
                        const as = Array.from(document.querySelectorAll('a[href*="/position/"]'));
                        return as.map(a => a.href).filter(h => h && h.includes('/position/'));
                    }""")
                    seen = set()
                    unique_links = [u for u in links if u not in seen and not seen.add(u)]
                    count = len(unique_links)
                    print(f"   스크롤 {scroll_num + 1}/{max_scrolls} — 로드된 고유 카드: {count}개")
                    if count >= target_count:
                        print(f"   → 목표 {target_count}개 도달")
                        break
                    new_height = page.evaluate("document.body.scrollHeight")
                    if new_height == prev_height and count > 0:
                        time.sleep(0.5)
                        new_height = page.evaluate("document.body.scrollHeight")
                    if new_height == prev_height:
                        break
                html = page.content()
                browser.close()
            jobs = self._extract_jobs_from_jumpit_html(html, job_role=job_role or '전체')
            seen_links = set()
            unique_jobs = []
            for j in jobs:
                link = j.get('link')
                if link and link not in seen_links:
                    seen_links.add(link)
                    unique_jobs.append(j)
                    if len(unique_jobs) >= target_count:
                        break
            print(f"✅ 무한 스크롤 리스트 수집 완료: 고유 {len(unique_jobs)}개")
            return unique_jobs
        except Exception as e:
            print(f"   ⚠️ 무한 스크롤 리스트 수집 실패: {e}")
            return []

    def _find_positions_list_in_json(self, obj, depth=0, max_depth=15):
        """JSON 트리를 재귀 탐색해 포지션처럼 보이는 리스트(객체에 id/title 등) 찾기"""
        if depth > max_depth:
            return None
        if isinstance(obj, list):
            if len(obj) == 0:
                return None
            first = obj[0]
            if isinstance(first, dict):
                has_id = 'id' in first or 'positionId' in first or 'recruitNo' in first
                has_title = 'title' in first or 'positionTitle' in first or 'jobTitle' in first
                has_company = 'company' in first or 'companyName' in first
                if has_id or (has_title and (has_company or 'link' in first or 'url' in first)):
                    return obj
            return None
        if isinstance(obj, dict):
            for v in obj.values():
                found = self._find_positions_list_in_json(v, depth + 1, max_depth)
                if found:
                    return found
        return None

    def _extract_jobs_from_jumpit_data(self, data, job_role='전체'):
        """__NEXT_DATA__ 등 JSON에서 포지션 리스트 추출"""
        jobs = []
        try:
            props = data.get('props', {}).get('pageProps') or data.get('pageProps') or data
            raw_list = (
                props.get('positions') or props.get('positionList') or
                props.get('jobs') or props.get('recruitList')
            )
            if not raw_list and isinstance(props.get('dehydratedState'), dict):
                qs = props.get('dehydratedState', {}).get('queries') or []
                for q in qs:
                    state = (q or {}).get('state', {}) or {}
                    data_inner = state.get('data') if isinstance(state, dict) else None
                    if isinstance(data_inner, dict):
                        raw_list = data_inner.get('positions') or data_inner.get('positionList') or data_inner.get('jobs')
                    if raw_list:
                        break
            if not raw_list:
                raw_list = self._find_positions_list_in_json(data)
            if not raw_list:
                raw_list = []
            for item in (raw_list if isinstance(raw_list, list) else []):
                job = self._normalize_jumpit_job(item, job_role=job_role)
                if job:
                    jobs.append(job)
        except Exception as e:
            print(f"   ⚠️ JSON 파싱 중 오류: {e}")
        return jobs

    def _normalize_jumpit_job(self, item, job_role='전체'):
        """점핏 API/JSON 항목을 공통 job 딕셔너리로 변환"""
        if not isinstance(item, dict):
            return None
        try:
            title = item.get('title') or item.get('positionTitle') or item.get('jobTitle') or ''
            company = item.get('company', {}).get('name', '') if isinstance(item.get('company'), dict) else item.get('companyName') or item.get('company') or ''
            if not company and isinstance(item.get('company'), str):
                company = item.get('company', '')
            pos_id = str(item.get('id') or item.get('positionId') or item.get('recruitNo') or item.get('positionNo') or '')
            if not title and not pos_id:
                return None
            link = item.get('url') or item.get('link') or f"{self.jumpit_base_url}/position/{pos_id}" if pos_id else ''
            if link and not link.startswith('http'):
                link = f"{self.jumpit_base_url}{link}" if link.startswith('/') else f"{self.jumpit_base_url}/position/{pos_id}"
            location = '지역 없음'
            if isinstance(item.get('location'), str):
                location = item.get('location')
            elif isinstance(item.get('locations'), list) and item['locations']:
                location = ', '.join(str(x) for x in item['locations'][:3])
            career = item.get('career') or item.get('careerLevel') or item.get('experience') or '경력 없음'
            return {
                'job_role': title,
                'title': company,
                'company': company,
                'location': location,
                'career': career,
                'education': item.get('education') or '학력 없음',
                'work_type': item.get('employmentType') or item.get('workType') or '근무형태 없음',
                'deadline': item.get('deadline') or item.get('endDate') or '',
                'link': link,
                'rec_idx': pos_id,
                'crawled_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'company_years': '',
                'tech_stack': '',
                'main_tasks': '',
                'qualifications': '',
                'preferred': '',
                'benefits': '',
                'recruitment_process': '',
            }
        except Exception:
            return None

    def _parse_card_text(self, full_text):
        """카드 한 덩어리 텍스트를 title, company, tech_stack, location, career 등으로 분리"""
        t = (full_text or '').strip()
        out = {'deadline': '', 'company': '', 'title': '', 'tech_stack': '', 'location': '지역 없음', 'career': '경력 없음'}
        if not t or len(t) < 4:
            return out
        # D-8 같은 마감 배지
        badge = re.match(r'^(D-\d+)', t)
        if badge:
            out['deadline'] = badge.group(1)
            t = t[badge.end():].strip()
        # 끝에서부터: 경력 → 지역 → 기술스택 순으로 제거
        career_m = re.search(r'(신입|경력\s*[\d~년]+)\s*$', t)
        if career_m:
            out['career'] = career_m.group(1).strip()
            t = t[:career_m.start()].strip()
        loc_m = re.search(r'((?:서울|경기|인천|부산|대구|대전|광주|세종|제주)[가-힣0-9\s,·]*)\s*$', t)
        if loc_m:
            out['location'] = loc_m.group(1).strip()
            t = t[:loc_m.start()].strip()
        tech_m = re.search(r'([\w/·\s]+(?:·\s*[\w/]+\s*)+)', t)
        if tech_m:
            out['tech_stack'] = tech_m.group(1).strip().replace('·', ',').replace(' ,', ',').strip()
            t = (t[:tech_m.start()] + t[tech_m.end():]).strip()
        # 남은 부분: 회사명(한글) + 직무제목 (예: 에스피에이치B2B 프로젝트 개발팀 신입)
        remainder = t.strip()
        if remainder:
            company_m = re.match(r'^([가-힣]+)', remainder)
            if company_m:
                out['company'] = company_m.group(1)
                rest = remainder[company_m.end():].strip()
                out['title'] = rest if rest else remainder
            else:
                out['title'] = remainder
        return out

    def _parse_list_card_selectors(self, card):
        """카드(BeautifulSoup 요소) 내부에서 데드라인·job_role·회사명만 셀렉터로 추출.
        - 데드라인: span.czeWCl (또는 class*='czeWCl')
        - job_role: h2.position_card_info_title
        - 회사명: 데드라인 span이 아닌 span (회사이름)
        """
        out = {'deadline': '', 'job_role': '', 'company': ''}
        if not card:
            return out
        deadline_el = card.select_one('span.czeWCl') or card.select_one('span[class*="czeWCl"]') or card.select_one('span[class*="sc-a0b0873a-0"]')
        if deadline_el:
            out['deadline'] = (deadline_el.get_text(strip=True) or '').strip()
        title_el = card.select_one('h2.position_card_info_title')
        if title_el:
            out['job_role'] = (title_el.get_text(strip=True) or '').strip()
        for span in card.select('span'):
            classes = span.get('class') or []
            if 'czeWCl' in classes:
                continue
            if 'sc-a0b0873a-0' in classes:
                continue
            t = (span.get_text(strip=True) or '').strip()
            if t and len(t) < 100:
                out['company'] = t
                break
        return out

    def _extract_jobs_from_jumpit_html(self, html, job_role='전체'):
        """점핏 HTML에서 포지션 링크/카드로 공고 추출. 카드 내 데드라인·job_role·회사명은 셀렉터로 추출."""
        jobs = []
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.select('a[href*="/position/"]'):
            href = a.get('href', '')
            match = re.search(r'/position/(\d+)', href)
            if not match:
                continue
            pos_id = match.group(1)
            link = f"{self.jumpit_base_url}/position/{pos_id}" if not href.startswith('http') else href.split('?')[0]
            raw_text = a.get_text(strip=True) or ''
            if len(raw_text) < 2 or len(raw_text) > 500:
                continue
            parsed = self._parse_list_card_selectors(a)
            fallback = self._parse_card_text(raw_text)
            if not parsed['job_role'] and not parsed['company']:
                parsed['deadline'] = parsed['deadline'] or fallback['deadline']
                parsed['job_role'] = fallback['title']
                parsed['company'] = fallback['company']
            job = {
                'job_role': parsed['job_role'] or '',
                'title': parsed['company'] or '',
                'company': parsed['company'] or '',
                'location': fallback.get('location') or '지역 없음',
                'career': fallback.get('career') or '경력 없음',
                'education': '학력 없음',
                'work_type': '근무형태 없음',
                'deadline': parsed['deadline'] or '',
                'link': link,
                'rec_idx': pos_id,
                'crawled_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'company_years': '',
                'tech_stack': fallback.get('tech_stack') or '',
                'main_tasks': '',
                'qualifications': '',
                'preferred': '',
                'benefits': '',
                'recruitment_process': '',
            }
            jobs.append(job)
        # 중복 제거 (같은 rec_idx)
        seen = set()
        unique = []
        for j in jobs:
            if j['rec_idx'] not in seen:
                seen.add(j['rec_idx'])
                unique.append(j)
        return unique

    def _parse_position_detail_from_next_data(self, data):
        """__NEXT_DATA__에서 상세 필드 추출 (기술스택, 주요업무, 자격요건 등)"""
        result = {
            'position_title': '',
            'company_name': '',
            'company_years': '',
            'tech_stack': '',
            'main_tasks': '',
            'qualifications': '',
            'preferred': '',
            'benefits': '',
            'recruitment_process': '',
            'career': '',
            'education': '',
            'deadline': '',
            'location': '',
        }
        try:
            props = data.get('props', {}).get('pageProps', data)
            pos = props.get('position') or props.get('positionDetail') or props.get('data')
            if not isinstance(pos, dict) and isinstance(props.get('dehydratedState'), dict):
                for q in (props.get('dehydratedState', {}).get('queries') or []):
                    state = (q or {}).get('state', {})
                    data_obj = state.get('data') or {}
                    if isinstance(data_obj, dict) and (data_obj.get('title') or data_obj.get('id')):
                        pos = data_obj
                        break
            if not isinstance(pos, dict):
                pos = props if isinstance(props, dict) else {}

            # 직무 제목·회사명 (job_role / title 보정용)
            result['position_title'] = (pos.get('title') or pos.get('positionTitle') or pos.get('jobTitle') or '').strip()
            company_obj = pos.get('company') if isinstance(pos.get('company'), dict) else {}
            result['company_name'] = (company_obj.get('name', '') if company_obj else pos.get('companyName') or pos.get('company') or '')
            if isinstance(result['company_name'], str):
                result['company_name'] = result['company_name'].strip()
            else:
                result['company_name'] = ''

            def to_text(val):
                if val is None:
                    return ''
                if isinstance(val, str):
                    return val.strip()
                if isinstance(val, list):
                    return '\n'.join(to_text(x) for x in val).strip()
                if isinstance(val, dict) and val.get('name'):
                    return str(val.get('name', '')).strip()
                return str(val).strip()

            def list_to_text(items, sep='\n'):
                if not items:
                    return ''
                if isinstance(items, str):
                    return items
                return sep.join(to_text(x) for x in items if to_text(x))

            # 기술스택: techStack, skillTags, technologies, tech_stack 등
            tech = pos.get('techStack') or pos.get('skillTags') or pos.get('technologies') or pos.get('tech_stack') or []
            if isinstance(tech, str):
                result['tech_stack'] = tech
            else:
                result['tech_stack'] = list_to_text(tech, ', ') or list_to_text(tech)

            # 주요업무: mainTasks, mainTasksList, responsibilities, main_tasks
            main = pos.get('mainTasks') or pos.get('mainTasksList') or pos.get('responsibilities') or pos.get('main_tasks')
            result['main_tasks'] = list_to_text(main) if main else ''

            # 자격요건: qualifications, requirements, qualification
            qual = pos.get('qualifications') or pos.get('requirements') or pos.get('qualification')
            result['qualifications'] = list_to_text(qual) if qual else ''

            # 우대사항: preferred, preferredQualifications, preferredRequirements
            pref = pos.get('preferred') or pos.get('preferredQualifications') or pos.get('preferredRequirements') or pos.get('우대사항')
            result['preferred'] = list_to_text(pref) if pref else ''

            # 복지 및 혜택: benefits, welfare, perks
            ben = pos.get('benefits') or pos.get('welfare') or pos.get('perks') or pos.get('복지')
            result['benefits'] = list_to_text(ben) if ben else ''

            # 채용절차 및 기타: recruitmentProcess, process, applicationGuide
            proc = pos.get('recruitmentProcess') or pos.get('process') or pos.get('applicationGuide') or pos.get('채용절차')
            result['recruitment_process'] = list_to_text(proc) if proc else to_text(proc)

            # 업력 (회사 설립/경력 년수)
            company_obj = pos.get('company') if isinstance(pos.get('company'), dict) else {}
            result['company_years'] = to_text(
                company_obj.get('companyYears') or company_obj.get('yearsInBusiness') or
                company_obj.get('업력') or pos.get('companyYears') or pos.get('업력')
            )

            # 경력 / 학력 / 마감일 / 근무지역
            result['career'] = to_text(pos.get('career') or pos.get('careerLevel') or pos.get('experience') or result['career'])
            result['education'] = to_text(pos.get('education') or pos.get('educationLevel') or result['education'])
            result['deadline'] = to_text(pos.get('deadline') or pos.get('endDate') or pos.get('dueDate') or result['deadline'])
            result['location'] = to_text(pos.get('location') or pos.get('workLocation') or pos.get('address') or pos.get('workPlace') or result['location'])

            # 주소가 객체인 경우 (addressDetail 등)
            addr = pos.get('addressDetail') or pos.get('address')
            if isinstance(addr, dict):
                result['location'] = to_text(addr.get('fullAddress') or addr.get('address') or addr.get('name')) or result['location']
            elif addr and not result['location']:
                result['location'] = to_text(addr)

            return result
        except Exception as e:
            print(f"   ⚠️ 상세 JSON 파싱 오류: {e}")
            return None

    def _parse_position_detail_from_html(self, html):
        """HTML에서 섹션별로 상세 정보 추출 (__NEXT_DATA__ 없을 때)"""
        result = {
            'company_years': '',
            'tech_stack': '',
            'main_tasks': '',
            'qualifications': '',
            'preferred': '',
            'benefits': '',
            'recruitment_process': '',
            'career': '',
            'education': '',
            'deadline': '',
            'location': '',
        }
        soup = BeautifulSoup(html, 'html.parser')
        # 업력: dl.details 내 dt "업력" 다음 dd 텍스트 (예: 18년차(2009년 6월 설립))
        dt_up = soup.find('dt', string=re.compile(re.escape('업력')))
        if dt_up:
            dd = dt_up.find_next_sibling('dd') or dt_up.find_next('dd')
            if dd:
                result['company_years'] = (dd.get_text(strip=True) or '').strip()
        # div.position_info 내 dl > dt / dd: 기술스택, 주요업무, 자격요건, 우대사항, 복지 및 혜택, 채용절차
        section_labels = {
            '기술스택': 'tech_stack',
            '주요업무': 'main_tasks',
            '자격요건': 'qualifications',
            '우대사항': 'preferred',
            '복지 및 혜택': 'benefits',
            '채용절차 및 기타 지원 유의사항': 'recruitment_process',
        }
        position_info = soup.select_one('div.position_info')
        scope = position_info if position_info else soup
        for dt in scope.find_all('dt'):
            label_text = (dt.get_text(strip=True) or '').strip()
            if not label_text:
                continue
            for label, key in section_labels.items():
                if label == label_text or label in label_text:
                    dd = dt.find_next_sibling('dd') or dt.find_next('dd')
                    if dd:
                        raw = dd.get_text(separator='\n', strip=True) or ''
                        if key == 'tech_stack':
                            result[key] = raw.replace('\n', ', ').strip()
                        else:
                            result[key] = raw.strip()
                    break
        # 경력/학력/마감일/근무지역: dl > dt/dd (포지션 경력·학력·마감일·근무지역 정보 블록)
        meta_labels = {'경력': 'career', '학력': 'education', '마감일': 'deadline', '근무지역': 'location'}
        for dt in soup.find_all('dt'):
            label_text = (dt.get_text(strip=True) or '').strip()
            if label_text not in meta_labels:
                continue
            dd = dt.find_next_sibling('dd') or dt.find_next('dd')
            if dd:
                result[meta_labels[label_text]] = (dd.get_text(separator=' ', strip=True) or '').strip()
        return result

    def _enrich_jobs_with_details_playwright(self, jobs, max_details=20, list_url=None):
        """Playwright로 각 카드(상세 페이지) 접속 → 로딩 대기 → 상세 데이터 추출. list_url 있으면 리스트→상세→이전 페이지 순회."""
        if not HAS_PLAYWRIGHT or not jobs:
            return jobs
        to_fetch = jobs[:max_details] if max_details else jobs
        total = len(to_fetch)
        print(f"\n📋 카드별 상세 수집 (브라우저에서 각 카드 접속): 최대 {total}건")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                if list_url:
                    page.goto(list_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(1)
                for i, job in enumerate(to_fetch):
                    link = job.get('link')
                    if not link:
                        continue
                    try:
                        print(f"   [{i + 1}/{total}] 카드 접속 중: {job.get('title', '')[:40]}...")
                        page.goto(link, wait_until="domcontentloaded", timeout=20000)
                        try:
                            page.wait_for_selector('script#__NEXT_DATA__', timeout=10000, state='attached')
                        except Exception:
                            pass  # __NEXT_DATA__ 없으면 HTML 폴백으로 진행
                        html = page.content()
                        next_data = self._parse_next_data(html)
                        if next_data:
                            detail = self._parse_position_detail_from_next_data(next_data)
                        else:
                            detail = self._parse_position_detail_from_html(html)
                        if detail:
                            # 상세에서 직무·회사명 있으면 job_role / title 보정 (리스트 파싱 오류 해소)
                            pt = (detail.get('position_title') or '').strip()
                            if pt:
                                job['job_role'] = pt
                            cn = (detail.get('company_name') or '').strip()
                            if cn:
                                job['title'] = cn
                                job['company'] = cn
                            for k in ('company_years', 'tech_stack', 'main_tasks', 'qualifications', 'preferred', 'benefits', 'recruitment_process'):
                                job[k] = (detail.get(k) or '').strip()
                            for k in ('career', 'education', 'deadline', 'location'):
                                v = (detail.get(k) or '').strip()
                                if v:
                                    job[k] = v
                        if list_url:
                            page.go_back()
                            time.sleep(0.5)
                    except Exception as e:
                        print(f"   ⚠️ [{i + 1}] 상세 수집 실패: {e}")
                    time.sleep(1)
                browser.close()
        except Exception as e:
            print(f"   ⚠️ Playwright 상세 수집 실패: {e}")
        print("✅ 상세 수집 완료!")
        return jobs

    def enrich_jobs_with_details(self, jobs, max_details=50, list_url=None):
        """리스트 카드 → 각 카드(상세 페이지) Playwright로 접속 후 기술스택·주요업무 등 수집 (Playwright 전용). list_url 있으면 상세 후 이전 페이지로 복귀."""
        if not jobs:
            return jobs
        if not HAS_PLAYWRIGHT:
            print("\n⚠️ 상세 수집은 Playwright 필요. pip install playwright && playwright install chromium")
            return jobs
        return self._enrich_jobs_with_details_playwright(jobs, max_details=max_details, list_url=list_url)

    def save_to_csv(self, jobs, filename=None):
        """결과를 csv로 저장"""
        if not jobs:
            print("저장할 데이터가 없습니다.")
            return
        
        if not filename:
            # 아무런 경로가 없으면 현재 이 python 파일이 있는 곳에 저장됩니다.
            filename = f"점핏_공고_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        df = pd.DataFrame(jobs)
        df.drop(columns=['keyword', 'work_type', 'crawled_at', 'rec_idx', 'title'], errors='ignore', inplace=True)
        # job_role: "채용" 제거
        if 'job_role' in df.columns:
            df['job_role'] = df['job_role'].fillna('').astype(str).str.replace('채용', '', regex=False).str.strip()
        # location: "지도보기", "·", "주소복사"/"주소 복사" 제거
        if 'location' in df.columns:
            loc = df['location'].fillna('').astype(str)
            for s in ('지도보기', '·', '주소복사', '주소 복사'):
                loc = loc.str.replace(s, '', regex=False)
            df['location'] = loc.str.replace(r'\s+', ' ', regex=True).str.strip()
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"{len(jobs)}개 공고를 {filename}에 저장하였습니다.")
        return filename
    
    def _get_keyword_stats(self, jobs):
        """직무별 통계 생성"""
        role_counts = {}
        for job in jobs:
            role = job.get('job_role', '기타')
            role_counts[role] = role_counts.get(role, 0) + 1
        stats = [f"{k}({v}개)" for k, v in role_counts.items()]
        return ", ".join(stats)

    def run_advanced_crawler(self, fetch_details=True, max_details=200, job_roles=None):
        """점핏: 리스트 수집 → 각 공고 상세 페이지 방문해 기술스택·주요업무 등 수집"""
        print("🚀 크롤링 시작! (점핏)")

        if job_roles is None:
            job_roles = ['전체']
        elif isinstance(job_roles, str):
            job_roles = [job_roles]
        # 지원하는 직무만 필터
        job_roles = [r for r in job_roles if r in self.jumpit_job_roles]

        # 무한 스크롤 리스트 수집 (Playwright) 또는 페이지네이션 수집
        if HAS_PLAYWRIGHT and max_details >= 200:
            unique_jobs = self._fetch_jobs_list_infinite_scroll_playwright(
                target_count=max_details, job_role=job_roles[0], sort='popular'
            )
        else:
            all_jobs = []
            for job_role in job_roles:
                jobs = self.search_jobs_jumpit(sort='popular', max_pages=30, job_role=job_role, target_count=max_details)
                all_jobs.extend(jobs)
            unique_jobs = []
            seen_links = set()
            for job in all_jobs:
                if job.get('link') and job['link'] not in seen_links:
                    unique_jobs.append(job)
                    seen_links.add(job['link'])
            unique_jobs = unique_jobs[:max_details]

        print(f"\n🎉 리스트에서 {len(unique_jobs)}개 고유 공고 확인!")
        print(f"   → 상세 수집 대상: {len(unique_jobs)}건 (각 카드 → 상세 페이지에서 기술스택·주요업무 등 수집)")

        list_url = None
        if job_roles:
            from urllib.parse import urlencode
            params = {'sort': 'popular'}
            role_param = self.jumpit_job_roles.get(job_roles[0])
            if role_param:
                params['job'] = role_param
            list_url = self.jumpit_positions_url + ('?' + urlencode(params) if params else '')

        if fetch_details and unique_jobs:
            unique_jobs = self.enrich_jobs_with_details(unique_jobs, max_details=max_details, list_url=list_url)

        # CSV 저장
        if unique_jobs:
            self.save_to_csv(unique_jobs)

        return unique_jobs

if __name__ == "__main__":
    crawler = JumpitCrawler()

    print("\n" + "="*60)
    print("🎯 점핏(jumpit.saramin.co.kr) 개발 직무별 크롤링")
    print("="*60)

    # 직무: None 또는 비면 '전체'만, 리스트로 지정하면 해당 직무만 수집
    # 예: job_roles=['서버/백엔드 개발자', '프론트엔드 개발자']
    job_roles = None  # 전체
    # job_roles = ['서버/백엔드 개발자', '프론트엔드 개발자']

    all_jobs = crawler.run_advanced_crawler(
        fetch_details=True,
        max_details=200,
        job_roles=job_roles
    )

    print(f"\n📊 최종 수집 결과:")
    print(f"   - 총 공고 수: {len(all_jobs)}")
    if all_jobs:
        print(f"   - 첫 번째 공고: {all_jobs[0].get('company', '-')} (직무: {all_jobs[0].get('job_role', '-')})")
    print(f"   - CSV 저장 완료")
