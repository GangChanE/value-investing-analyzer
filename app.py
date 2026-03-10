import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# ⚙️ 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="K-Value Oracle V1.2", page_icon="⚖️", layout="wide")

st.title("⚖️ The Quantum Oracle: 한국형 가치투자 분석기 V1.2")
st.markdown("야후 파이낸스의 오류를 제거하고 **'네이버 금융 데이터'**를 직접 파싱하는 극강의 보수적 가치 평가 엔진입니다.")

# ---------------------------------------------------------
# ⚙️ 사용자 입력 및 네이버 금융 크롤링 엔진
# ---------------------------------------------------------
ticker_input = st.text_input("분석할 한국 주식 종목코드 6자리를 입력하세요 (예: 005930)", "005930")
WACC = st.slider("요구수익률(WACC) 설정 (%) - 통상 8~10% 사용", min_value=5.0, max_value=15.0, value=8.0, step=0.5) / 100

def get_naver_financials(code):
    """네이버 금융에서 실시간 주가 및 기업실적분석(EPS, BPS, ROE) 데이터를 직접 스크래핑합니다."""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. 기업명 및 현재가 파싱
        name_tag = soup.select_once('.wrap_company h2 a')
        price_tag = soup.select_once('p.no_today span.blind')
        
        if not name_tag or not price_tag:
            return None
            
        name = name_tag.text
        current_price = float(price_tag.text.replace(',', ''))
        
        # 2. 기업실적분석 표 파싱 (Pandas read_html 활용)
        dfs = pd.read_html(res.text, encoding='euc-kr')
        fin_df = dfs[3] # 4번째 표가 보통 실적 분석표
        
        # 첫 번째 열을 인덱스로 설정
        idx_col = fin_df.iloc[:, 0].values
        
        # 항목 이름이 포함된 행 인덱스 찾기
        eps_row = [i for i, val in enumerate(idx_col) if 'EPS' in str(val)][0]
        bps_row = [i for i, val in enumerate(idx_col) if 'BPS' in str(val)][0]
        roe_row = [i for i, val in enumerate(idx_col) if 'ROE' in str(val)][0]
        
        # 최신 값 추출 (에러 발생 시 무시하고 숫자만 추출)
        eps_latest = pd.to_numeric(fin_df.iloc[eps_row, 1:10], errors='coerce').dropna().iloc[-1]
        bps_latest = pd.to_numeric(fin_df.iloc[bps_row, 1:10], errors='coerce').dropna().iloc[-1]
        roe_latest = pd.to_numeric(fin_df.iloc[roe_row, 1:10], errors='coerce').dropna().iloc[-1] / 100.0
        
        # 과거 4년치 EPS 역사 (통계적 DCF 추세용)
        eps_history = pd.to_numeric(fin_df.iloc[eps_row, 1:5], errors='coerce').dropna().values
        
        return {
            'name': name,
            'price': current_price,
            'eps': eps_latest,
            'bps': bps_latest,
            'roe': roe_latest,
            'eps_history': eps_history
        }
    except Exception as e:
        return None

if st.button("🔍 내재 가치 분석 실행"):
    if len(ticker_input) != 6 or not ticker_input.isdigit():
        st.warning("⚠️ 종목코드는 숫자 6자리여야 합니다. (예: 005930)")
        st.stop()
        
    with st.spinner(f"[{ticker_input}] 네이버 금융 재무 데이터 추출 및 4대 엔진 가동 중..."):
        fin_data = get_naver_financials(ticker_input)
        
        if not fin_data:
            st.error("❌ 종목을 찾을 수 없거나 데이터 추출에 실패했습니다. 상장폐지 여부나 코드를 확인하세요.")
            st.stop()
            
        current_price = fin_data['price']
        eps = fin_data['eps']
        bps = fin_data['bps']
        roe = fin_data['roe']
        eps_history = fin_data['eps_history']
        
        if eps <= 0 or bps <= 0:
            st.error(f"❌ {fin_data['name']}은(는) 현재 적자 기업이거나 자본잠식 상태입니다. (보수적 가치평가는 흑자 기업에만 적용됩니다.)")
            st.stop()

        # ---------------------------------------------------------
        # 🧠 4대 보수적 가치평가 엔진
        # ---------------------------------------------------------
        
        # 1. 벤저민 그레이엄 공식
        graham_value = np.sqrt(22.5 * eps * bps)
        
        # 2. 수익력 가치 (EPV)
        epv_value = eps / WACC
        
        # 3. 잔여이익모델 (RIM)
        rim_value = bps + (bps * (roe - WACC) / WACC) if roe > WACC else bps

        # 4. 통계적 보수형 DCF (EPS 성장률 기반 대리 모델)
        dcf_value = 0
        if len(eps_history) >= 3 and all(e > 0 for e in eps_history):
            growth_rates = np.diff(eps_history) / eps_history[:-1]
            mu = np.mean(growth_rates)
            sigma = np.std(growth_rates)
            
            conservative_g = mu - (0.52 * sigma)
            g = max(0.02, min(conservative_g, 0.15)) # 최소 2%, 최대 15% 성장 캡
            
            present_value = 0
            for year in range(1, 6):
                eps_t = eps * ((1 + g) ** year)
                present_value += eps_t / ((1 + WACC) ** year)
            
            tv = (eps * ((1 + g) ** 5) * (1 + 0.025)) / (WACC - 0.025)
            present_value += tv / ((1 + WACC) ** 5)
            dcf_value = present_value
        else:
            dcf_value = epv_value # 과거 적자 기록이 있으면 EPV로 대체

        # ---------------------------------------------------------
        # 📊 결과 종합 및 판별
        # ---------------------------------------------------------
        models = {'Graham': graham_value, 'EPV': epv_value, 'RIM': rim_value, 'Stat-DCF': dcf_value}
        strict_fair_value = min(models.values())
        
        st.subheader(f"📊 {fin_data['name']} ({ticker_input}) 가치 평가 결과")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("현재 주가", f"₩{current_price:,.0f}")
        col2.metric("가장 보수적인 적정 주가", f"₩{strict_fair_value:,.0f}")
        
        margin_of_safety = ((strict_fair_value - current_price) / strict_fair_value) * 100
        col3.metric("안전 마진 (Margin of Safety)", f"{margin_of_safety:,.1f}%")
        
        if current_price < strict_fair_value:
            col4.success("🟢 STRONG BUY (저평가)")
        elif current_price < strict_fair_value * 1.1: 
            col4.warning("🟡 HOLD (적정 가치)")
        else:
            col4.error("🔴 SELL (고평가)")

        st.markdown("---")
        st.markdown("### ⚙️ 4대 엔진 개별 산출가")
        
        st.info(f"**1. 그레이엄 내재가치 (Graham):** ₩{graham_value:,.0f} \n\n (성장 배제. EPS와 BPS만을 이용한 전통적 가치)")
        st.info(f"**2. 잔여이익모델 (RIM):** ₩{rim_value:,.0f} \n\n (요구수익률 초과 이익 가치화. 버핏의 선호 방식)")
        st.info(f"**3. 수익력 가치 (EPV):** ₩{epv_value:,.0f} \n\n (미래 성장률 0%로 가정한 가장 가혹한 모델)")
        st.info(f"**4. 통계적 보수형 DCF:** ₩{dcf_value:,.0f} \n\n (과거 변동성 기반 '하위 30%' 보수적 성장률 적용)")

st.markdown("---")
st.caption("Data Source: Naver Finance | 본 대시보드는 재무제표 기반의 기계적/보수적 가치 평가를 수행합니다.")
